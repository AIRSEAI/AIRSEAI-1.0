from abc import ABC, abstractmethod
import json
import logging
import requests
import yaml
import os
import re
import openai
from openai import OpenAI

class Task_Planner(ABC):
    def __init__(self):
        self._msg = None
        self._re_msg = None

    @abstractmethod
    def llm_processor(self, prompt):
        pass

    def get_tasks(self, inst):
        prompt = self._build_prompt(inst)
        # print(prompt)
        self._msg = self.llm_processor(prompt)
        self._re_msg = self._msg
        # print(self._msg)
        actions = self.llm_response_to_actions(self._msg)
        return actions

    def replan_get_tasks(self, error_id, history_info):
        prompt = self._build_replan_prompt(error_id, history_info)
        # print(prompt)
        msg = self.llm_processor(prompt)
        # print(msg)
        self._re_msg[error_id] = msg[0]
        # print(self._re_msg)
        actions = self.llm_response_to_actions(self._re_msg)
        return actions

    def _load_yaml_map(self, filename):
        with open(filename, 'r') as file:
            yaml_dict = yaml.safe_load(file)

        yaml_map = {}
        for key, obj in yaml_dict.items():
            yaml_map[obj['label']] = [obj['x'], obj['y'], obj['theta']]

        return yaml_map

    def llm_response_to_actions(self, msg):
        actions_list = msg
        processed_actions = []

        for action in actions_list:
            go_to_action = action.get("go_to", "")
            if go_to_action:
                go_to_table, go_to_coords = go_to_action.split("[")
                go_to_table = go_to_table.strip()
                go_to_coords = [float(coord) for coord in go_to_coords.strip("]").split(", ")]
                processed_actions.append(['go_to', [go_to_table, go_to_coords]])

            pick_up_action = action.get("pick_up", "")
            if pick_up_action:
                processed_actions.append(['pick_up', [pick_up_action]])

            place_action = action.get("place", "")
            if place_action:
                place_table, place_coords = place_action.split("[")
                place_table = place_table.strip()
                place_coords = [float(coord) for coord in place_coords.strip("]").split(", ")]
                processed_actions.append(['go_to', [place_table, place_coords]])
                processed_actions.append(['place', [pick_up_action]])

        return processed_actions

    def _validate_json(self, content):
        try:
            data = json.loads(content)
            return data
        except json.JSONDecodeError:
            return None

    def _build_prompt(self, inst):
        prompt = (
            self._prompt_context + json.dumps(self._semantic_map) + self._prompt_skills +
            self._task_instruction + inst + self._output_format + self._note1
        )
        return prompt

    def _build_replan_prompt(self, error_id, history_info):

        failed_task = self._msg[error_id]
        failed_task_json = json.dumps(failed_task, indent=4)

        history_information = """

## Historical Feedback: ## 
"""
        for item in history_info:
            table, location, obj = item
            history_information += f"""
There is no {obj} on the {table}: {location}.
"""
        prompt = (
            self._re_prompt_context + json.dumps(self._semantic_map) + self._failed_task + failed_task_json
            + history_information  + self._requirement
        )
        return prompt

class LLM_Task_Planner(Task_Planner):

    def __init__(self, model_name, semantic_map):
        self.model_name = model_name
        self._semantic_map = self._load_yaml_map(semantic_map)
        self._prompt_context = """
## Instruction: ##
You are a skilled robotic task planner, proficient in breaking down complex, long-term tasks into atomic actions. 
The robot has a mobile base and an arm. The environment is represented by a semantic map in JSON format:
{
    "coordinate table": [x, y, angle]
}
where "coordinate table" means different types of tables, "x" and "y" are positional coordinates, and "angle" represents the table’s orientation. 

Here is a detailed Semantic Map:
"""
        self._prompt_skills = """

## Skill ##
Break down the language instruction into subtasks, using exact names from the semantic map and only using coordinate_table in the "go_to" and "place" subtasks.
go_to [coordinate table1], pick_up [object], place [coordinate table2]
"""
        self._task_instruction = """
## Task Instruction ##
Based on the given task the Semantic Map and Instruction, break down the task into subtasks. The Instruction is as follows:
"""
        self._output_format = """

## Output Format ##
Ensure all output is in JSON format, following the structure below:
[
    {
        "go_to": "coordinate table1 [x1, y1, angle1]",
        "pick_up": "object1",
        "place": "coordinate table2 [x2, y2, angle2]"
    },
    ...
]
"""
        self._note1 = """
## Notes: ##
The output must be JSON data only.

If multiple target objects are involved, include multiple sets of task steps.
"""
        self._re_prompt_context = """
You are a robotic task planning assistant responsible for dynamically adjusting the "go_to" command on failed tasks based on environmental information and historical feedback.
The environment is represented by a semantic map in JSON format:

{
    "coordinate table": [x, y, angle]
}

where "coordinate table" means different types of tables, "x" and "y" are positional coordinates, and "angle" represents the table’s orientation. 

Here is a detailed Semantic Map:
"""
        self._failed_task = """

## Failed tasks ##
"""
        self._requirement = """
#### Requirements ####
Ensure that the response is always in valid JSON format and follows this structure:
[
    {
        "go_to": "coordinate table1 [x1, y1, angle1]",
        "pick_up": "object1",
        "place": "coordinate table2 [x2, y2, angle2]"
    }
]
Ensure that:
    1. The "go_to" and "place" fields should correctly reference tables and their respective coordinates.
    2. If an object is not found at the specified table (as indicated in the failed task or historical feedback), avoid suggesting any actions involving that object.
    3. Change only the 'go_to' statement and leave the other statements unchanged.
    4. The output must be JSON data only.
"""

class GPT4_Task_Planner(LLM_Task_Planner):

    def __init__(self, api_key, api_url, semantic_map):
        super().__init__("GPT-4", semantic_map)
        self._api_key = api_key
        self._api_url = api_url

    def llm_processor(self, prompt):
        client = OpenAI(api_key=self._api_key, base_url=self._api_url)
        while True:
            try:
                completion = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": ""},
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                response_json = completion.choices[0].message.content
                data = re.sub(r'```(json)?', '', response_json).strip()
                data = self._validate_json(data)
                if data is not None:
                    return data
                else:
                    logging.info("Received invalid JSON content, retrying...")
            except json.JSONDecodeError:
                logging.info("Received invalid JSON content, retrying...")
                continue

class LLAMA_Task_Planner(LLM_Task_Planner):

    def __init__(self, url, semantic_map):
        super().__init__("LLAMA", semantic_map)
        self._url = url

    def llm_processor(self, prompt):
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json"
        }
        json_input = {
            "model": "llama3.1:70b-instruct-fp16",
            "messages": [{
                "role": "user",
                "content": prompt
            }],
            "stream": False
        }
        while True:
            response = requests.post(self._url, headers=headers, data=json.dumps(json_input))
            response_json = response.json()
            content = response_json.get("message", {}).get("content", "")
            # print(content)
            data = self._validate_json(content)
            if data is not None:
                return data
            else:
                print("Received invalid JSON content, retrying...")
