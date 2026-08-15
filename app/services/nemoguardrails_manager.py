from transformers import pipeline
from nemoguardrails.llm.helpers import get_llm_instance_wrapper
from nemoguardrails.llm.providers import (
    HuggingFacePipelineCompatible,
    register_llm_provider,
)
import time
from langchain_openai import ChatOpenAI
from nemoguardrails import RailsConfig, LLMRails
from settings.setting import GUARDRAILS_CONFIG_PATH, GUARDRAILS_OLLAMA_CONFIG_PATH, KRUTRIM_MODEL, KRUTRIM_TEMPERATURE, KRUTRIM_BASE_URL, KRUTRIMAI_API_KEY, GUARDRAILS_OLA_CONFIG_PATH
from logs.logger_setup import setup_logger
from langchain_openai import ChatOpenAI
from settings.setting import *

class NemoGuardrailsManager:
    def __init__(self, llm_model, llm_tokenizer):
        self.params = {"temperature": 0.3, "max_new_tokens": 150}
        self.pipe = pipeline(
            model=llm_model,
            task="text-generation",
            tokenizer=llm_tokenizer,
            truncation=True,
            **self.params,
        )
        self.llm = HuggingFacePipelineCompatible(pipeline=self.pipe, model_kwargs=self.params)
        self.HFPipelineForGuardrails = get_llm_instance_wrapper(
            llm_instance=self.llm, llm_type="hf_pipeline_for_guardrails"
        )
        register_llm_provider("hf_pipeline_for_guardrails", self.HFPipelineForGuardrails)
        self.config = RailsConfig.from_path(GUARDRAILS_CONFIG_PATH)
        self.guard_rail = LLMRails(config=self.config)
        self.logger = setup_logger("nemo_guardrails")

    async def run_guardrails(self, user_input):
        try:
            start_time = time.time()
            response = await self.guard_rail.generate_async(
                messages=[{"role": "user",
                           "content": user_input}]
            )
            end_time = time.time()

            self.logger.info(f"Required time for the guardrails in hugging face: {end_time - start_time} seconds")
            # print(f"Required time for the guardrails: {end_time - start_time}")
            final_response = response['content']
            return final_response

        except Exception as e:
            self.logger.exception(f"Exception {e} occurred")

class NemoGuardrailsManagerOLA:
    def __init__(self):
        self.llm = ChatOpenAI(api_key=KRUTRIMAI_API_KEY, base_url=KRUTRIM_BASE_URL, model='meta-llama/Meta-Llama-3.1-8B-Instruct',
                              temperature=KRUTRIM_TEMPERATURE)
        # self.OLAPipelineForGuardrails = get_llm_instance_wrapper(
        #     llm_instance=self.llm, llm_type="ola_pipeline_for_guardrails"
        # )
        # register_llm_provider("ola_pipeline_for_guardrails", self.OLAPipelineForGuardrails)
        self.config = RailsConfig.from_path(GUARDRAILS_OLA_CONFIG_PATH)
        self.guard_rail = LLMRails(config=self.config, llm=self.llm)
        print(f"Nemo Guardrails in Ola krutrim\n")
        self.logger = setup_logger("nemo_guardrails_in_ola_krutrim")

    async def run_guardrails(self, user_input):
        try:
            start_time = time.time()
            response = await self.guard_rail.generate_async(
                messages=[{"role": "user",
                           "content": user_input}]
            )
            end_time = time.time()
            self.logger.info(f"Required time for the guardrails in ola krutrim: {end_time - start_time} seconds")
            # print(f"Required time for the guardrails: {end_time - start_time}")
            final_response = response['content']
            return final_response

        except Exception as e:
            self.logger.exception(f"Exception {e} occurred")

class NemoGuardrailsManagerOllama:
    def __init__(self):
        self.config = RailsConfig.from_path(GUARDRAILS_OLLAMA_CONFIG_PATH)
        self.guard_rail = LLMRails(config=self.config)
        self.logger = setup_logger("nemo_guardrails_with_ollama")

    async def run_guardrails(self, user_input):
        try:
            start_time = time.time()
            response = await self.guard_rail.generate_async(
                messages=[{"role": "user",
                           "content": user_input}]
            )
            end_time = time.time()

            self.logger.info(f"Required time for the guardrails in ollama: {end_time - start_time} seconds")
            # print(f"Required time for the guardrails: {end_time - start_time}")
            final_response = response['content']
            return final_response

        except Exception as e:
            self.logger.exception(f"Exception {e} occurred")

    def run_guardrails_sync(self, user_input):
        try:
            start_time = time.time()
            response = self.guard_rail.generate(
                messages=[{"role": "user",
                           "content": user_input}]
            )
            end_time = time.time()

            self.logger.info(f"Required time for the guardrails: {end_time - start_time} seconds")
            # print(f"Required time for the guardrails: {end_time - start_time}")
            final_response = response['content']
            return final_response

        except Exception as e:
            self.logger.exception(f"Exception {e} occurred")
