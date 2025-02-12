import json
import logging
from openai import OpenAI
from pathlib import Path
class api_client:
    def __init__(self,cost_type):
        package_root = Path(__file__).resolve().parent.parent
        config_path = package_root / 'config' / 'llm_api_config.json'
        self.config_path = config_path
        self.cost_type = cost_type

        with open(self.config_path, 'r',encoding='utf-8') as f:
            config = json.load(f)
            self.llm_prompt = config.get("prompt")
            self.max_chat_history_text_length = config.get("max_chat_history_text_length")

            if self.cost_type == 'low_cost':
                api_call = config.get("low_cost_api_call", {})
            elif self.cost_type == 'high_cost':
                api_call = config.get("high_cost_api_call", {})
            elif self.cost_type == 'reasoner_model':
                api_call = config.get("reasoner_model_api_call", {})
                self.max_chat_history_text_length = api_call.get("max_chat_history_text_length")
            
            api_type = api_call.get("api_type")
            self.llm_api_key = api_call.get("api_key")
            self.llm_base_url = api_call.get("base_url")
            self.llm_model_name = api_call.get("model")

            if api_type == 'openai':
                self.llm_api_client = OpenAI(
                    api_key = self.llm_api_key,
                    base_url = self.llm_base_url
                )
                
class ai_reply:
    def __init__(self):
        self.users_dict = {}
        self.users_count = 1
        self.reply_count = 0
        self.total_lowcost_token = 0
        self.total_highcost_token = 0
        self.total_reasoner_model_token = 0

        self.low_cost_api_client = api_client('low_cost')
        self.high_cost_api_client = api_client('high_cost')
        self.reasoner_model_api_client = api_client('reasoner_model')

        self.chat_history = [{'role': 'system', 'content': self.low_cost_api_client.llm_prompt}]
        self.max_chat_history_text_length = self.low_cost_api_client.max_chat_history_text_length
        self.reasoner_model_max_chat_history_text_length = self.reasoner_model_api_client.max_chat_history_text_length
        self.last_chat_history_length = len(self.chat_history[0])

    #根据字数返回应当截断的聊天历史的索引
    def get_truncate_chat_history_index(self,max_length):
        temp_index = 1
        if len(self.chat_history) > 2: 
            current_chat_history_length = self.last_chat_history_length + len(self.chat_history[-1]['content']) + len(self.chat_history[-2]['content'])
            if current_chat_history_length > max_length:
                while current_chat_history_length > max_length:
                    current_chat_history_length -= len(self.chat_history[temp_index]['content']) + len(self.chat_history[temp_index + 1]['content'])
                    temp_index += 2
        return temp_index
    
    #根据字数截断聊天历史
    def truncate_chat_history(self,max_length):
        current_chat_history_length = self.last_chat_history_length + len(self.chat_history[-1]['content']) + len(self.chat_history[-2]['content'])
        if current_chat_history_length > max_length:
            temp_index = 1
            while current_chat_history_length > max_length:
                current_chat_history_length -= len(self.chat_history[temp_index]['content']) + len(self.chat_history[temp_index + 1]['content'])
                temp_index += 2
            del self.chat_history[ 1:temp_index ]
        self.last_chat_history_length = current_chat_history_length
    
    def api_call_reasoner_model(self,text):
        truncated_index = self.get_truncate_chat_history_index(self.reasoner_model_max_chat_history_text_length)
        chat_history_for_reasoner = self.chat_history[:1] + self.chat_history[truncated_index:] + [{'role': 'user', 'content': text}]
        self.chat_history.append({'role': 'user', 'content': text})
        print(chat_history_for_reasoner)
        completion = self.reasoner_model_api_client.llm_api_client.chat.completions.create(
            model = self.reasoner_model_api_client.llm_model_name,
            messages = chat_history_for_reasoner
        )
        text_json = json.loads(completion.model_dump_json())
        return text_json

    def api_call_llm(self,text,cost_type):
        self.chat_history.append({'role': 'user', 'content': text})
        if cost_type == 'low_cost':
            client = self.low_cost_api_client
        elif cost_type == 'high_cost':
            client = self.high_cost_api_client
        completion = client.llm_api_client.chat.completions.create(
            model = client.llm_model_name,
            messages = self.chat_history
        )
        text_json = json.loads(completion.model_dump_json())
        return text_json

    def ai_reply(self,cost_type,member_id,message):
        if member_id not in self.users_dict:
            self.users_dict[member_id] = self.users_count
            self.users_count += 1
        member = self.users_dict[member_id]
        
        combined_message_text = f'用户{member}说: {message}'
        try:
            if cost_type == 'low_cost':
                reply_message_json = self.api_call_llm(combined_message_text,'low_cost')
                self.total_lowcost_token += reply_message_json['usage']['total_tokens']
            elif cost_type == 'high_cost':
                reply_message_json = self.api_call_llm(combined_message_text,'high_cost')
                self.total_highcost_token += reply_message_json['usage']['total_tokens']
            elif cost_type == 'reasoner_model':
                reply_message_json = self.api_call_reasoner_model(combined_message_text)
                self.total_reasoner_model_token += reply_message_json['usage']['total_tokens']
        except Exception as e:
            del self.chat_history[-1]
            logging.error(f'模型调用失败:{e}')
            return '模型调用失败'
        
        reply_message_plaintext = reply_message_json['choices'][0]['message']['content']
        self.chat_history.append({'role': 'assistant', 'content': reply_message_plaintext})
        self.reply_count += 1

        self.truncate_chat_history(self.max_chat_history_text_length)
        print(f'\n低成本token数:{self.total_lowcost_token},高成本token数:{self.total_highcost_token},推理模型token数:{self.total_reasoner_model_token},聊天历史长度:{len(self.chat_history)},回复次数:{self.reply_count},聊天历史文字数:{self.last_chat_history_length}')
        return reply_message_plaintext + f"\n\n模型:{reply_message_json['model']},记录中包含{ (len(self.chat_history) -1) // 2}轮对话,回答消耗token数:{reply_message_json['usage']['total_tokens']}"

if __name__ == '__main__':
    reply = ai_reply()
    while 1:
        text = input()
        print(reply.ai_reply('reasoner_model',1,text))