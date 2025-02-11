import json
from openai import OpenAI
from pathlib import Path
class api_client:
    def __init__(self,cost_type):
        package_root = Path(__file__).resolve().parent.parent
        config_path = package_root / 'config' / 'llm_api_config.json'
        self.type = type
        self.config_path = config_path
        self.cost_type = cost_type
    def get_api_client(self):
        with open(self.config_path, 'r',encoding='utf-8') as f:
            config = json.load(f)
            llm_prompt = config.get("prompt")
            if self.cost_type == 'low_cost':
                api_call = config.get("low_cost_api_call", {})
            elif self.cost_type == 'high_cost':
                api_call = config.get("high_cost_api_call", {})
            api_type = api_call.get("api_type")
            llm_api_key = api_call.get("api_key")
            llm_base_url = api_call.get("base_url")
            llm_model_name = api_call.get("model")
            if api_type == 'openai':
                client = OpenAI(
                    api_key = llm_api_key,
                    base_url = llm_base_url
                )
                return client,llm_model_name,llm_prompt
                
class ai_reply:
    def __init__(self):
        self.users_dict = {}
        self.users_count = 1
        self.average_reply_context_count = 0
        self.reply_count = 0
        self.total_lowcost_token = 0
        self.total_highcost_token = 0

        self.low_cost_api_client,self.low_cost_llm_model_name,prompt = api_client('low_cost').get_api_client()
        self.high_cost_api_client,self.high_cost_llm_model_name,prompt = api_client('high_cost').get_api_client()
        self.chat_history = [{'role': 'system', 'content': prompt}]
        self.last_chat_history_length = len(self.chat_history[0])

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

    def ai_lowcost_reply(self,text):
        self.chat_history.append({'role': 'user', 'content': text})
        completion = self.low_cost_api_client.chat.completions.create(
            model = self.low_cost_llm_model_name,
            messages = self.chat_history
        )
        text_json = json.loads(completion.model_dump_json())
        self.total_lowcost_token += text_json['usage']['total_tokens']
        return text_json
    
    def ai_highcost_reply(self,text):
        self.chat_history.append({'role': 'user', 'content': text})
        completion = self.high_cost_api_client.chat.completions.create(
            model = self.high_cost_llm_model_name,
            messages = self.chat_history
        )
        text_json = json.loads(completion.model_dump_json())
        self.total_highcost_token += text_json['usage']['total_tokens']
        return text_json

    def ai_reply(self,cost_type,member_id,message):
        if member_id not in self.users_dict:
            self.users_dict[member_id] = self.users_count
            self.users_count += 1
        member = self.users_dict[member_id]
        
        combined_message_text = f'用户{member}说: {message}'
        if cost_type == 'low_cost':
            reply_message_json = self.ai_lowcost_reply(combined_message_text)
        elif cost_type == 'high_cost':
            reply_message_json = self.ai_highcost_reply(combined_message_text)
        reply_message_plaintext = reply_message_json['choices'][0]['message']['content']
        self.chat_history.append({'role': 'assistant', 'content': reply_message_plaintext})
        
        self.reply_count += 1
        self.truncate_chat_history(2600)
        print(f'\n低成本token数:{self.total_lowcost_token},高成本token数:{self.total_highcost_token},聊天历史长度:{len(self.chat_history)},回复次数:{self.reply_count},聊天历史文字数:{self.last_chat_history_length}')
        return reply_message_plaintext + f"\n\n模型:{reply_message_json['model']},记录中包含{ (len(self.chat_history) -1) // 2}轮对话,回答消耗token数:{reply_message_json['usage']['total_tokens']}"

if __name__ == '__main__':
    reply = ai_reply()
    while 1:
        text = input()
        print(reply.ai_reply('low_cost',1,text))