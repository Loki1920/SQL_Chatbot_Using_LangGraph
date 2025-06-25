import os
import requests
import streamlit as st

# 3. Import LangChain, LangGraph
from langchain_groq import ChatGroq
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from typing import Literal
from urllib.parse import quote_plus
from dotenv import load_dotenv
load_dotenv()  # This loads the .env file

# Streamlit page configuration
st.set_page_config(page_title="SQL Agent", page_icon="🗄️", layout="wide")
st.title("🗄️ Natural Language to SQL Agent")

# Function to get credentials securely
def get_credentials():
    """Get credentials from Streamlit secrets or environment variables"""
    try:
        # Try Streamlit secrets first (for deployment)
        if hasattr(st, 'secrets'):
            return {
                'POSTGRES_HOST': st.secrets.get("POSTGRES_HOST", "localhost"),
                'POSTGRES_PORT': st.secrets.get("POSTGRES_PORT", "5432"),
                'POSTGRES_DB': st.secrets.get("POSTGRES_DB", "chinook"),
                'POSTGRES_USER': st.secrets.get("POSTGRES_USER", "postgres"),
                'POSTGRES_PASSWORD': st.secrets.get("POSTGRES_PASSWORD", ""),
                'GROQ_API_KEY': st.secrets.get("GROQ_API_KEY", "")
            }
    except:
        pass
    
    # Fallback to environment variables (for local development)
    return {
        'POSTGRES_HOST': os.getenv("POSTGRES_HOST", "localhost"),
        'POSTGRES_PORT': os.getenv("POSTGRES_PORT", "5432"),
        'POSTGRES_DB': os.getenv("POSTGRES_DB", "chinook"),
        'POSTGRES_USER': os.getenv("POSTGRES_USER", "postgres"),
        'POSTGRES_PASSWORD': os.getenv("POSTGRES_PASSWORD", ""),
        'GROQ_API_KEY': os.getenv("GROQ_API_KEY", "")
    }

# Get credentials
credentials = get_credentials()

# PostgreSQL connection setup
POSTGRES_HOST = credentials['POSTGRES_HOST']
POSTGRES_PORT = credentials['POSTGRES_PORT']
POSTGRES_DB = credentials['POSTGRES_DB']
POSTGRES_USER = credentials['POSTGRES_USER']
POSTGRES_PASSWORD = credentials['POSTGRES_PASSWORD']
GROQ_API_KEY = credentials['GROQ_API_KEY']

# Validate required credentials
if not GROQ_API_KEY:
    st.error("❌ GROQ_API_KEY is not set. Please configure your credentials.")
    st.info("For local development, set environment variables. For deployment, use Streamlit secrets.")
    st.stop()

if not POSTGRES_PASSWORD:
    st.error("❌ Database credentials are not properly configured.")
    st.stop()

# URL encode the password to handle special characters like @, #, etc.
encoded_password = quote_plus(POSTGRES_PASSWORD)
encoded_user = quote_plus(POSTGRES_USER)

# Create PostgreSQL connection string with encoded credentials
postgres_url = f"postgresql://{encoded_user}:{encoded_password}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
#conn_st = st.connection(name="postgres", type='sql', url = postgres_url)
# Set Groq API key in environment
os.environ["GROQ_API_KEY"] = GROQ_API_KEY

# Initialize components only once using session state
if 'agent' not in st.session_state:
    with st.spinner("Initializing SQL Agent..."):
        try:
            # 4. Initialize Groq LLM and DB
            llm = ChatGroq(
                groq_api_key=GROQ_API_KEY,
                model="llama3-70b-8192",
                temperature=0
            )
            db = SQLDatabase.from_uri(postgres_url)
            toolkit = SQLDatabaseToolkit(db=db, llm=llm)
            tools = toolkit.get_tools()

            # 5. Define agent nodes
            get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")
            get_schema_node = ToolNode([get_schema_tool], name="get_schema")
            run_query_tool = next(tool for tool in tools if tool.name == "sql_db_query")
            run_query_node = ToolNode([run_query_tool], name="run_query")

            def list_tables(state: MessagesState):
                tool_call = {
                    "name": "sql_db_list_tables",
                    "args": {},
                    "id": "abc123",
                    "type": "tool_call",
                }
                tool_call_message = AIMessage(content="", tool_calls=[tool_call])
                list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
                tool_message = list_tables_tool.invoke(tool_call)
                response = AIMessage(f"Available tables: {tool_message.content}")
                return {"messages": [tool_call_message, tool_message, response]}

            def call_get_schema(state: MessagesState):
                try:
                    llm_with_tools = llm.bind_tools([get_schema_tool])
                    response = llm_with_tools.invoke(state["messages"])
                    return {"messages": [response]}
                except Exception as e:
                    # Fallback: directly call schema tool for all tables
                    tables = db.get_usable_table_names()[:3]  # Limit to first 3 tables
                    schema_info = db.get_table_info_no_throw(tables)
                    return {"messages": [AIMessage(content=f"Schema information: {schema_info}")]}

            generate_query_system_prompt = f"""
            You are an agent designed to interact with a SQL database.
            Given an input question, create a syntactically correct {db.dialect} query to run,
            then look at the results of the query and return the answer. Unless the user
            specifies a specific number of examples they wish to obtain, always limit your
            query to at most 5 results.

            You can order the results by a relevant column to return the most interesting
            examples in the database. Never query for all the columns from a specific table,
            only ask for the relevant columns given the question.

            where ever possible return the available data in tabular format.

            DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.
            """

            def generate_query(state: MessagesState):
                try:
                    system_message = SystemMessage(content=generate_query_system_prompt)
                    llm_with_tools = llm.bind_tools([run_query_tool])
                    messages = [system_message] + state["messages"]
                    response = llm_with_tools.invoke(messages)
                    return {"messages": [response]}
                except Exception as e:
                    # Fallback: generate query without tool binding
                    system_message = SystemMessage(content=generate_query_system_prompt + "\n\nPlease provide the SQL query directly in your response.")
                    messages = [system_message] + state["messages"]
                    response = llm.invoke(messages)
                    return {"messages": [response]}

            check_query_system_prompt = f"""
            You are a SQL expert with a strong attention to detail.
            Double check the {db.dialect} query for common mistakes, including:
            - Using NOT IN with NULL values
            - Using UNION when UNION ALL should have been used
            - Using BETWEEN for exclusive ranges
            - Data type mismatch in predicates
            - Properly quoting identifiers
            - Using the correct number of arguments for functions
            - Casting to the correct data type
            - Using the proper columns for joins

            If there are any of the above mistakes, rewrite the query. If there are no mistakes,
            just reproduce the original query.

            You will call the appropriate tool to execute the query after running this check.
            """

            def check_query(state: MessagesState):
                try:
                    system_message = SystemMessage(content=check_query_system_prompt)
                    last_message = state["messages"][-1]
                    
                    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                        tool_call = last_message.tool_calls[0]
                        user_message = HumanMessage(content=tool_call["args"]["query"])
                        llm_with_tools = llm.bind_tools([run_query_tool])
                        response = llm_with_tools.invoke([system_message, user_message])
                        response.id = last_message.id
                        return {"messages": [response]}
                    else:
                        # If no tool calls, just return the message as is
                        return {"messages": [last_message]}
                except Exception as e:
                    return {"messages": [AIMessage(content=f"Error in query checking: {str(e)}")]}

            def should_continue(state: MessagesState):
                messages = state["messages"]
                last_message = messages[-1]
                if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                    return "check_query"
                else:
                    return END

            # 6. Build the workflow graph
            builder = StateGraph(MessagesState)
            builder.add_node("list_tables", list_tables)
            builder.add_node("call_get_schema", call_get_schema)
            builder.add_node("get_schema", get_schema_node)
            builder.add_node("generate_query", generate_query)
            builder.add_node("check_query", check_query)
            builder.add_node("run_query", run_query_node)

            builder.add_edge(START, "list_tables")
            builder.add_edge("list_tables", "call_get_schema")
            builder.add_edge("call_get_schema", "get_schema")
            builder.add_edge("get_schema", "generate_query")
            builder.add_conditional_edges("generate_query", should_continue)
            builder.add_edge("check_query", "run_query")
            builder.add_edge("run_query", "generate_query")

            st.session_state.agent = builder.compile()
            st.success("✅ SQL Agent initialized successfully!")
            
        except Exception as e:
            st.error(f"❌ Failed to initialize SQL Agent: {str(e)}")
            st.stop()

# Streamlit UI
st.markdown("Ask questions about your database in natural language!")

# Input form
with st.form("query_form"):
    question = st.text_area(
        "Enter your question:",
        placeholder="e.g., Show me the top 5 customers by total purchases",
        height=100
    )
    submitted = st.form_submit_button("Ask SQL Agent", type="primary")

if submitted and question:
    with st.spinner("Processing your question..."):
        try:
            state = {"messages": [HumanMessage(content=question)]}
            answer = None
            step_count = 0
            max_steps = 10  # Prevent infinite loops
            
            for step in st.session_state.agent.stream(state, stream_mode="values"):
                step_count += 1
                if step_count > max_steps:
                    st.warning("Maximum steps reached. Stopping execution.")
                    break
                    
                last_msg = step["messages"][-1]
                
                # Look for final answer
                if (isinstance(last_msg, AIMessage) and 
                    last_msg.content and 
                    not getattr(last_msg, "tool_calls", None) and
                    "Available tables:" not in last_msg.content):
                    answer = last_msg.content
                    break
            
            if answer:
                st.success("Answer:")
                st.write(answer)
            else:
                st.warning("I couldn't generate an answer for your question. Please try rephrasing your question.")
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            # Show more detailed error information
            import traceback
            st.text("Detailed error:")
            st.code(traceback.format_exc())

elif submitted and not question:
    st.warning("Please enter a question.")

# Sidebar with information
with st.sidebar:
    st.header("Database Info")
    st.write(f"**Database:** {POSTGRES_DB}")
    st.write(f"**Host:** {POSTGRES_HOST}")
    st.write(f"**Port:** {POSTGRES_PORT}")
    
    st.header("How to use")
    st.write("1. Enter your question in natural language")
    st.write("2. Click 'Ask SQL Agent'")
    st.write("3. The agent will convert your question to SQL and return the results")
    
    st.header("Example Questions")
    st.write("- Show me the top 5 customers by total purchases")
    st.write("- What are the most popular music genres?")
    st.write("- List all albums by a specific artist")
    st.write("- How many tracks are in each playlist?")
