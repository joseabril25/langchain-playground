# RETRIEVAL CHAIN - for document retrieval
from langchain_community.document_loaders import WebBaseLoader
from langchain_openai import ChatOpenAI, OpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain, create_history_aware_retriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain.tools.retriever import create_retriever_tool

loader = WebBaseLoader("https://docs.smith.langchain.com/user_guide")
llm = OpenAI()

#1. Load the documents
docs = loader.load()
#2. Create the embeddings
embeddings = OpenAIEmbeddings()
#3. Create the retriever
text_splitter = RecursiveCharacterTextSplitter()
#4. Split the text
documents = text_splitter.split_documents(docs)
#5. Create the vector store
vector = FAISS.from_documents(documents, embeddings)
#6. Create the retriever
retriever = vector.as_retriever()

# search tool
retriever_tool = create_retriever_tool(
    retriever,
    "langsmith_search",
    "Search for information about LangSmith. For any questions about LangSmith, you must use this tool!",
)

tools = [retriever_tool]

# Create the context dynamically by retrieving documents from the vector store
def create_context_from_documents(input_query):
    docs = retriever.invoke(input_query)
    context = "\n\n".join([doc.page_content for doc in docs])
    return context

#7. Create the prompt
prompt = ChatPromptTemplate.from_template("""Answer the following question based only on the provided context:

<context>
{context}
</context>

Question: {input}""")

#8. Create the document chain
document_chain = create_stuff_documents_chain(llm, prompt)

retriever_prompt = ChatPromptTemplate.from_messages([
    ("system", "Answer the user's questions based on the below context:\n\n{context}"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}"),
])
#9. Create the retrievar chain - for history
retriever_chain = create_history_aware_retriever(llm, retriever, retriever_prompt)
#10. Create the retrieval chain (document + history)
retrieval_chain = create_retrieval_chain(retriever_chain, document_chain)


chat_history = [
  HumanMessage(content="Can LangSmith help test my LLM applications?"), 
  AIMessage(content="Yes!"), 
  HumanMessage(content="How?"),
  AIMessage(content="LangSmith provides a platform for LLM application development, monitoring, and testing. It supports various workflows and stages of the application development lifecycle, including prototyping, debugging, initial test sets, comparison views, playground environment for rapid iteration and experimentation, beta testing, capturing feedback, annotating traces, adding runs to datasets, and production monitoring and A/B testing. It also offers features such as online evaluations and automations, threads view for multi-turn applications, and monitoring charts to track key metrics over time. Additionally, LangSmith allows for tag and metadata grouping for A/B testing changes in prompt, model, or retrieval strategy. These features make it easier to understand and improve the performance of LLM applications."),
  HumanMessage(content="What else?"),
  AIMessage(content="There is no specific information provided in the context to answer this question."),
  HumanMessage(content="What is prototyping in the from the user guide?"),
  AIMessage(content="Prototyping is the process of quickly experimenting and testing different aspects of an LLM (Language Model) application, such as prompts, model types, and retrieval strategies. This allows developers to understand how the model is performing and debug any issues that may arise."),
  ]
input_query = "When developing new LLM applications, what does the document suggest?"
context = create_context_from_documents(input_query)
result = retrieval_chain.invoke({
    "chat_history": chat_history,
    "context": context,
    "input": input_query,
})

print(result["answer"])