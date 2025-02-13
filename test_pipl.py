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
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)  # 프로젝트 루트 디렉토리
        if project_root not in sys.path:  # 프로젝트 루트 디렉토리를 sys.path에 추가
            sys.path.insert(0, project_root)
        from config import config_llm  # config_llm 임포트
        LLM = config_llm.LLM
        thread_id = uuid.uuid4()  # 랜덤 Thread 생성

        os.environ["TAVILY_API_KEY"] = "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"
        # tool_internetSearch = TavilySearchResults(max_results=10)
        class LoggingTavilySearchResults(TavilySearchResults):
            # 동기 실행 시 오버라이드
            def _run(self, query: str):
                print(f"[Tool Call] TavilySearchResults 동기 호출됨: query = {query}")
                return super()._run(query)
            
            # 비동기 실행 시 오버라이드
            async def _arun(self, query: str):
                print(f"[Tool Call] TavilySearchResults 비동기 호출됨: query = {query}")
                return await super()._arun(query)

        tool_internetSearch = DuckDuckGoSearchResults(name="duckduckgoSearch", description='인터넷검색') 
        @tool
        def multiply(a: float, b: float) -> float:
            """Call to add a * b"""
            print(f"[Tool Call] multiplu called with a={a}, b={b}")
            return a * b

        @tool
        def adder(a: float, b: float) -> float:
            """Call to add a+b"""
            print(f"[Tool Call] adder called with a={a}, b={b}")
            return a + b

        @tool
        def minus(a: float, b: float) -> float:
            """Call to minus a-b"""
            print(f"[Tool Call] minus called with a={a}, b={b}")
            return a - b

        @tool
        def divider(a: float, b: float) -> float:
            """Call to add a/b"""
            print(f"[Tool Call] divider called with a={a}, b={b}")
            return a / b

        # tools = [tool_internetSearch, multiply_tool, adder]
        tools = [LoggingTavilySearchResults(max_results=5), multiply, adder,divider,minus]

        prompt = "You are a helpful assistant."
        agent_executor = create_react_agent(LLM, tools, prompt=prompt)

        # State 정의
        class PlanExecute(TypedDict):
            input: str
            plan: List[str]
            past_steps: Annotated[List[Tuple], operator.add]
            response: str


        class Plan(BaseModel):
            """Plan to follow in future"""
            steps: List[str] = Field(
                description="different steps to follow, should be in sorted order"
            )
            
        planner_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """For the given objective, come up with a simple step by step plan. \
        This plan should involve individual tasks, that if executed correctly will yield the correct answer. Do not add any superfluous steps. \
        The result of the final step should be the final answer. Make sure that each step has all the information needed - do not skip steps.
        """,
                ),
                ("placeholder", "{messages}"),
            ]
        )
        planner = planner_prompt | LLM.with_structured_output(Plan)

        class Response(BaseModel):
            """Response to user."""
            response: str

        class Act(BaseModel):
            """Action to perform."""
            action: Union[Response, Plan] = Field(
                description="Action to perform. If you want to respond to user, use Response. "
                            "If you need to further use tools to get the answer, use Plan."
            )

        replanner_prompt = ChatPromptTemplate.from_template(
            """For the given objective, come up with a simple step by step plan. \
        This plan should involve individual tasks, that if executed correctly will yield the correct answer. Do not add any superfluous steps. \
        The result of the final step should be the final answer. Make sure that each step has all the information needed - do not skip steps.

        Your objective was this:
        {input}

        Your original plan was this:
        {plan}

        You have currently done the follow steps:
        {past_steps}

        Update your plan accordingly. If no more steps are needed and you can return to the user, then respond with that. Otherwise, fill out the plan. Only add steps to the plan that still NEED to be done. Do not return previously done steps as part of the plan."""
        )
        replanner = replanner_prompt | LLM.with_structured_output(Act)

        async def execute_step(state: PlanExecute):
            plan = state["plan"]
            plan_str = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))
            task = plan[0]
            task_formatted = f"""For the following plan: {plan_str}\n\nYou are tasked with executing step {1}, {task}."""
            agent_response = await agent_executor.ainvoke(
                {"messages": [("user", task_formatted)]}
            )
            return {
                "past_steps": [(task, agent_response["messages"][-1].content)],
            }

        async def plan_step(state: PlanExecute):
            plan = await planner.ainvoke({"messages": [("user", state["input"])]})
            return {"plan": plan.steps}

        async def replan_step(state: PlanExecute):
            output = await replanner.ainvoke(state)
            if isinstance(output.action, Response):
                return {"response": output.action.response}
            else:
                return {"plan": output.action.steps}

        def should_end(state: PlanExecute):
            if "response" in state and state["response"]:
                return END
            else:
                return "agent"
            
        workflow = StateGraph(PlanExecute)
        workflow.add_node("planner", plan_step)
        workflow.add_node("agent", execute_step)
        workflow.add_node("replan", replan_step)

        workflow.add_edge(START, "planner")
        workflow.add_edge("planner", "agent")
        workflow.add_edge("agent", "replan")
        workflow.add_conditional_edges("replan", should_end, ["agent", END])
        self.config = {"recursion_limit": 50}   
        self.app = workflow.compile()


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

        input = {"input":user_message}
  
        async def run_with_tracing():
            final_response = None  # 최종 Agent 답변을 저장할 변수
            async for event in self.app.astream(input, config=self.config):
                
                # 플래너 노드 출력 (키: "planner")
                if "planner" in event:
                    plan_data = event["planner"].get("plan", [])
                    if plan_data:
                        print("\n" + "-"*20 + " Plan Node Output " + "-"*20)
                        for idx, step in enumerate(plan_data, 1):
                            formatted_step = step.replace("\n", "\n    ")
                            print(f"Step {idx}:\n    {formatted_step}\n")
                
                # 에이전트 노드 출력 (키: "agent")
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
                
                # 리플래너 노드 출력 (최종 응답 확인; 키: "replan")
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
