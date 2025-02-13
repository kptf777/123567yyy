import sys
import os
import uuid
import operator
import time
import json  # json 모듈 추가
from typing import Annotated, List, Tuple, Literal, Union
from typing_extensions import TypedDict

import nest_asyncio
nest_asyncio.apply()

import asyncio

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition, create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.tools import DuckDuckGoSearchResults

from pydantic import BaseModel, Field
from langchain import hub
from langchain.tools import tool
from langchain.agents import Tool, initialize_agent, AgentType
from langchain_core.prompts import ChatPromptTemplate

# LangSmith 트레이싱 임포트 및 환경변수 설정
from langsmith import trace  # LangSmith tracing 모듈

from typing import List, Union, Generator, Iterator
from pydantic import BaseModel
import requests
import os

class Pipeline:
    class Valves(BaseModel):
        # You can add your custom valves here.
        # You can add your custom valves here.
        AZURE_OPENAI_API_KEY: str
        AZURE_OPENAI_ENDPOINT: str
        AZURE_OPENAI_DEPLOYMENT_NAME: str
        AZURE_OPENAI_API_VERSION: str
        

    def __init__(self):
        self.name = "Azure OpenAI Pipeline Test"
        self.valves = self.Valves(
            **{
                "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY", "your-azure-openai-api-key-here"),
                "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT", "your-azure-openai-endpoint-here"),
                "AZURE_OPENAI_DEPLOYMENT_NAME": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "your-deployment-name-here"),
                "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
            }
        )
       pass


    async def on_startup(self):
        # This function is called when the server is started.
        print(f"on_startup:{__name__}")
        pass

    async def on_shutdown(self):
        # This function is called when the server is stopped.
        print(f"on_shutdown:{__name__}")
        pass

    def pipe(
            self, user_message: str, model_id: str, messages: List[dict], body: dict) -> Union[str, Generator, Iterator]:
                # This is where you can add your custom pipelines like RAG.

        input = {"input":user_message}
        async def run_with_tracing():
            final_response = None  # 최종 Agent 답변을 저장할 변수
            async for event in self.app.astream(input, config=self.config):
                if "planner" in event:
                    plan_data = event["planner"].get("plan", [])
                    if plan_data:
                        print("\n" + "-"*20 + " Plan Node Output " + "-"*20)
                        for idx, step in enumerate(plan_data, 1):
                            formatted_step = step.replace("\n", "\n    ")
                            print(f"Step {idx}:\n    {formatted_step}\n")
                
                if "agent" in event:
                    agent_data = event["agent"].get("past_steps", [])
                    if agent_data:
                        print("\n" + "-"*20 + " Agent Execution Output " + "-"*20)
                        for idx, (task, response) in enumerate(agent_data, 1):
                            formatted_task = task.replace("\n", "\n    ")
                            formatted_response = response.replace("\n", "\n    ")
                            print(f"\n-- Execution #{idx} --")
                            print("Task:")
                            print("    " + formatted_task)
                            print("\nAgent Response:")
                            print("    " + formatted_response)
                
                if "replan" in event:
                    replan_data = event["replan"]
                    if "response" in replan_data and replan_data["response"]:
                        final_response = replan_data["response"]
                        formatted_final = final_response.replace("\n", "\n    ")
                        print("\n" + "-"*20 + " Final Response " + "-"*20)
                        print("    " + formatted_final)
                        break
                    elif "plan" in replan_data:
                        updated_plan = replan_data["plan"]
                        if updated_plan:
                            print("\n" + "-"*20 + " Updated Plan from Replan Node " + "-"*20)
                            for idx, step in enumerate(updated_plan, 1):
                                formatted_step = step.replace("\n", "\n    ")
                                print(f"Step {idx}:\n    {formatted_step}\n")
            return final_response
        response=asyncio.run(run_with_tracing())
        return response
                    if "response" in replan_data and replan_data["response"]:
                        final_response = replan_data["response"]
                        formatted_final = final_response.replace("\n", "\n    ")
                        print("\n" + "-"*20 + " Final Response " + "-"*20)
                        print("    " + formatted_final)
                        break
                    elif "plan" in replan_data:
                        updated_plan = replan_data["plan"]
                        if updated_plan:
                            print("\n" + "-"*20 + " Updated Plan from Replan Node " + "-"*20)
                            for idx, step in enumerate(updated_plan, 1):
                                formatted_step = step.replace("\n", "\n    ")
                                print(f"Step {idx}:\n    {formatted_step}\n")
            return final_response
        response=asyncio.run(run_with_tracing())
        return response
