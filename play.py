# LLM CHAIN - language model
from langchain_openai import ChatOpenAI, OpenAI
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser, CommaSeparatedListOutputParser
from langchain_core.messages import HumanMessage, SystemMessage

# llm = ChatOpenAI()
output_parser = CommaSeparatedListOutputParser()

# prompt = ChatPromptTemplate.from_messages([
#     ("system", "You are a world class technical documentation writer."),
#     ("user", "{input}")
# ])

# chain = llm | prompt | output_parser

# chain.invoke({"input": "how can langsmith help with testing?"})
# ========================================

llm = OpenAI()
chat_model = ChatOpenAI()

# template = "You are a helpful assistant that translates {input_language} to {output_language}."
# human_template = "{text}"

# chat_prompt = ChatPromptTemplate.from_messages([
#     SystemMessage("You are a helpful assistant that translates {input_language} to {output_language}."),
#     HumanMessage("{text}")
# ])

# chat_prompt.format_messages(input_language="English", output_language="French", text="I love programming.")

template = "Generate a list of 5 {text}.\n\n{format_instructions}"

chat_prompt = ChatPromptTemplate.from_template(template)
chat_prompt = chat_prompt.partial(format_instructions=output_parser.get_format_instructions())
chain = chat_prompt | chat_model | output_parser
result = chain.invoke({"text": "colors"})
print(result)