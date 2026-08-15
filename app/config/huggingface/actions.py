import logging
from typing import Optional

from langchain_core.language_models.llms import BaseLLM

from nemoguardrails import RailsConfig
from nemoguardrails.actions.actions import ActionResult, action
from nemoguardrails.actions.llm.utils import llm_call
from nemoguardrails.context import llm_call_info_var
from nemoguardrails.llm.params import llm_params
from nemoguardrails.llm.taskmanager import LLMTaskManager
from nemoguardrails.llm.types import Task
from nemoguardrails.logging.explain import LLMCallInfo
from nemoguardrails.utils import new_event_dict
from langchain.prompts import PromptTemplate

log = logging.getLogger(__name__)


@action(is_system_action=True)
async def self_check_input(
    llm_task_manager: LLMTaskManager,
    context: Optional[dict] = None,
    llm: Optional[BaseLLM] = None,
    config: Optional[RailsConfig] = None,
    **kwargs,
):
    """Checks the input from the user.

    Prompt the LLM, using the `check_input` task prompt, to determine if the input
    from the user should be allowed or not.

    Returns:
        True if the input should be allowed, False otherwise.
    """

    _MAX_TOKENS = 30
    user_input = context.get("user_message")
    task = Task.SELF_CHECK_INPUT

    if user_input:
        prompt = llm_task_manager.render_task_prompt(
            task=task,
            context={
                "user_input": user_input,
            },
        )
        stop = llm_task_manager.get_stop_tokens(task=task)
        # max_tokens = llm_task_manager.get_max_tokens(task=task)
        # max_tokens = _MAX_TOKENS

        # Initialize the LLMCallInfo object
        llm_call_info_var.set(LLMCallInfo(task=task.value))
        # print(f"Task Value: {task.value}")

        # with llm_params(
        #     llm, temperature=0.3, max_tokens=max_tokens
        # ):

        response = await llm_call(llm, prompt, stop=stop)

        # print(f'Answer: {response}')
        
        # for sake of backward compatibility
        # if the output_parser is not registered we will use the default one
        # if llm_task_manager.has_output_parser(task):
        #     result = llm_task_manager.parse_task_output(task, output=response)

        # else:
        #     result = llm_task_manager.output_parsers["is_content_safe"](response)

        # is_safe, _ = result

        # if response == "Yes":
        #     return ActionResult(
        #         return_value=False,
        #         events=[
        #             new_event_dict(
        #                 "mask_prev_user_message", intent="unanswerable message"
        #             )
        #         ],
        #     )

        # return response

        # result = response.split('Answer:')[1]

        # print(f'Final result: {result}')
        # print("\n\n\n")

        answer = response.split('Answer: ')[1]
        found = answer.find('0')

        if found != -1:
          # print("Done")
          return True

        else: 
          return False

    else:
        return False    

@action(is_system_action=True)
async def check_greeting(
    llm_task_manager: LLMTaskManager,
    context: Optional[dict] = None,
    llm: Optional[BaseLLM] = None,
    config: Optional[RailsConfig] = None,
    **kwargs,
):
    # print("Successfully enter into the emotion and greeting")

    _MAX_TOKENS = 30
    user_input = context.get("user_message")
    POSITIVE_RESPONSE = 1
    NEGATIVE_RESPONSE = 0

    greeting_bool_prompt = f""" 
      Classify the given user message into one of the following categories:
      
      Return {POSITIVE_RESPONSE} if the message falls into these categories:
        Greeting (e.g., "Hello", "Hi there!")
        Acknowledgment (e.g., "Thanks", "Okay", "Got it")
        Welfare Inquiry (e.g., "How are you?", "Hope you're doing well")
        Expression of Happiness (e.g., "I'm so happy today!", "This is great!")
        Expression of Sadness (e.g., "I'm feeling down", "This is disappointing")
        Goodbye (e.g., "Goodbye", "See you later")

      Return {NEGATIVE_RESPONSE} for any message that is:

        A user ask or print about the previous question or answer or word then send the {NEGATIVE_RESPONSE} message
        A question about a topic, system, or process (e.g., "Which accounts can I see in the default view?")
        A request for information, explanation, or instruction (e.g., "Explain the default account settings.")
        A command or task request (e.g., "Show me the report.")

      for example:
        user_input_1: "Hello"
        Answer_1: 1

        user_input_2: "It was the great answer"
        Answer_2: 1

        user_input_3: "i am good"
        Answer_3: 1

        user_input_4: "How are you"
        Answer_4: 1

        user_input_5: "Good bye"
        Answer_5: 1

        user_input_6: "What is insurance carrier?"
        Answer_6: 0

        user_input_7: "What are the reasons of patient overpayment?"
        Answer_7: 0

        user_input_8: "how to fill the address?"
        Answer_8: 0

        user_input_9: "Why used the display?"
        Answer_9: 0

        user_input_10: "Which accounts i can see in default view"
        Answer_10: 0
        
        user_input_11: "1"
        Answer_11: 1
        
        user_input_12: "0"
        Answer_12: 1

      User Message: {user_input}

      Give the Answer only in {POSITIVE_RESPONSE} or {NEGATIVE_RESPONSE}.

      Answer:  
    """
    
    greeting_qa_bool_prompt = PromptTemplate.from_template(greeting_bool_prompt)

    if user_input:
        # print(f'User input: {user_input}')
        greeting_bool_final_prompt = greeting_qa_bool_prompt.format(user_input = user_input)

        response = await llm_call(llm, greeting_bool_final_prompt)

        # print(f'Answer: {response}')

        greeting_bool_result = response.split('Answer:')[1]

        # print('\n')

        # print(f'Final result: {greeting_bool_result}')
        # print("\n\n")

        # answer = response.split('Answer:')[1]
        # found = greeting_bool_result.find('Yes')

        if greeting_bool_result:
          # print("Greeting Done")
          return True

        else: 
          return False

@action(is_system_action=True)
def refuse_to_respond():
    return "Sorry i don't have the answer of this question. please rephrase or rewrite the query."

@action(is_system_action=True)
def run_with_chain():
    return "Valid"


@action(is_system_action=True)
async def generate_answer_of_greeting(llm_task_manager: LLMTaskManager,
    context: Optional[dict] = None,
    llm: Optional[BaseLLM] = None,
    config: Optional[RailsConfig] = None,
    **kwargs,
):

    # print("Successfully enter into for generating the answer of greeting")

    _MAX_TOKENS = 30
    user_input = context.get("user_message")

    greeting_prompt = """
      Below is a conversation between a helpful AI assistant and a user. 
      The bot is designed to generate human-like text based on the input that it receives. 
      The bot is talkative and provides lots of specific details. 
      If the bot does not know the answer to a question, it truthfully says it does not know.
      Return only the answer of the assistant do not predict the next user question and Answer
      Just give the only answer of the user question whatever user asked

      User Message = {user_input}

      Answer: 
    """

    greeting_answer_prompt = PromptTemplate.from_template(greeting_prompt)
    
    if user_input:
        # print(f'User input: {user_input}')
        greeting_bool_final_prompt = greeting_answer_prompt.format(user_input = user_input)

        response = await llm_call(llm, greeting_bool_final_prompt)

        # print(f'Answer: {response}')

        greeting_result = response.split('Answer:')[1]

        # print('\n')

        # print(f'Final result: {greeting_result}')
        # print("\n\n")

        # answer = response.split('Answer:')[1]

        return greeting_result

