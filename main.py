import base64
import os

import requests
import botpy
import json
import git
from tts.tts import return_tts_base64data
from ai_reply.reply_module import ai_reply
from botpy import logging
from openai import OpenAI
from botpy.ext.cog_yaml import read
from botpy.message import GroupMessage, Message

test_config = read(os.path.join(os.path.dirname(__file__), "config/config.yaml"))
_log = logging.get_logger()
group_session_dict = {}

def manage_group_session(group_id):
    if group_id not in group_session_dict:
        group_session_dict[group_id] = ai_reply()
    return group_session_dict[group_id]
def get_git_commit_hash():
    repo = git.Repo(os.path.dirname(__file__))
    return repo.head.object.hexsha

class MyClient(botpy.Client):
    async def on_ready(self):
        _log.info(f"robot 「{self.robot.name}」 on_ready!")
    async def on_group_at_message_create(self, message: GroupMessage):
        #tts模块
        member_id = message.author.member_openid
        group_id = message.group_openid
        reply = manage_group_session(group_id)

        if message.content[:5] == ' /tts':
            truncated_message_content = message.content[5:]
            base64_data = await return_tts_base64data(truncated_message_content)        
            
            uploadMedia = await message._api.post_group_base64file(
                group_openid=message.group_openid,
                file_type = 3,
                file_data = base64_data
            )
            messageResult = await message._api.post_group_message(
                group_openid=message.group_openid,
                msg_type=7,  # 7表示富媒体类型
                msg_id=message.id, 
                media=uploadMedia
            )

        elif message.content[:7] == ' /voice':
            truncated_message_content = message.content[7:]
            reply.ai_reply('low_cost',member_id,truncated_message_content)
            base64_data = await return_tts_base64data(reply.chat_history[-1]['content'])

            uploadMedia = await message._api.post_group_base64file(
                group_openid=message.group_openid,
                file_type = 3,
                file_data = base64_data
            )
            messageResult = await message._api.post_group_message(
                group_openid=message.group_openid,
                msg_type = 7,  # 7表示富媒体类型
                msg_id = message.id, 
                media = uploadMedia
            )
        
        elif message.content[:5] == ' /ver':
            messageResult = await message._api.post_group_message(
                group_openid=message.group_openid,
                msg_type = 0,  # 7表示富媒体类型
                msg_id = message.id, 
                content = f'当前版本commit hash：{get_git_commit_hash()}'
            )
        
        elif message.content[:7] == ' /reset':
            reply.chat_history = [reply.chat_history[0]]
            reply.last_chat_history_length = len(reply.chat_history[0])
            messageResult = await message._api.post_group_message(
                group_openid=message.group_openid,
                msg_type = 0,  # 7表示富媒体类型
                msg_id = message.id, 
                content = f'已清除当前聊天记录,{len(reply.chat_history)}'
            )
        
        #AI回复实现
        else:
            print(member_id)
            if message.content[:4] == ' /ds':
                cost_type = 'high_cost'
            elif message.content[:4] == ' /rm':
                cost_type = 'reasoner_model'
            else:
                cost_type = 'low_cost'
            messageResult = await message._api.post_group_message(
                group_openid=message.group_openid,
                msg_type = 0, 
                msg_id = message.id,
                content=f"{reply.ai_reply(cost_type,member_id,message.content)}")
        
        _log.info(messageResult)

if __name__ == "__main__":
    # 通过预设置的类型，设置需要监听的事件通道
    # intents = botpy.Intents.none()
    # intents.public_messages=True

    # 通过kwargs，设置需要监听的事件通道
    intents = botpy.Intents(public_messages=True)
    client = MyClient(intents=intents)
    client.run(appid=test_config["appid"], secret=test_config["secret"])