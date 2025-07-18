

# AI-Powered SQL Database Query Chatbot

## Overview
This project is an intelligent SQL query agent that allows users to interact with a PostgreSQL database using **natural language** queries. By leveraging **OpenAI's GPT-4** and **LangChain**, the system translates natural language inputs into SQL commands and executes them on a connected PostgreSQL database. The result is returned as a structured response, making database querying accessible for non-technical users.

## Key Features
- **Natural Language Querying**: Allows users to submit natural language queries (e.g., "Show me all records where the sales are above $5000"), which are then converted into SQL commands by the agent.
- **AI-Powered SQL Translation**: Uses **GPT-4** to understand and translate user queries into SQL, providing flexibility in interacting with the database without needing deep SQL knowledge.
- **PostgreSQL Integration**: The app securely connects to a PostgreSQL database and executes queries with dynamic inputs.
- **Error Handling**: Proper error handling for invalid inputs or queries, ensuring robust and reliable database interactions.
- **REST API**: The project exposes a simple RESTful API to accept queries and return results.

## Technologies Used
- **Python**: The primary language for building the API and handling logic.
- **Flask**: Used to create a RESTful API for query handling.
- **PostgreSQL**: The SQL database used to store and query data.
- **OpenAI GPT-4**: For natural language processing and query translation.
- **LangChain**: To facilitate communication between the language model and the database, utilizing its `SQLDatabaseToolkit`.

## Getting Started

### Prerequisites
To run the project, you will need the following installed:
- **Python 3.8+**
- **PostgreSQL** (configured with proper username, password, and a database)
- **OpenAI API Key** (for GPT-4)
- **Flask**

### Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/sql-query-agent.git
   cd sql-query-agent
   ```

2. **Install Dependencies**:
   Install the required Python packages using `pip`:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL Database**:
   Ensure that your PostgreSQL server is running, and you've created a database. Update the database credentials in the code:
   ```python
   db_username = os.getenv("DB_USERNAME", "your_db_username")
   db_password = os.getenv("DB_PASSWORD", "your_db_password")
   db_host = os.getenv("DB_HOST", "localhost")
   db_port = os.getenv("DB_PORT", "5432")
   db_name = os.getenv("DB_NAME", "your_db_name")
   ```

4. **Set up OpenAI API Key**:
   You will need an OpenAI API key to access GPT-4. You can set the key as an environment variable or directly in the code:
   ```bash
   export OPENAI_API_KEY='your_openai_api_key'
   ```

5. **Run the Flask App**:
   Start the Flask app by running:
   ```bash
   python app.py
   ```

   This will start the server at `http://0.0.0.0:5000`.

### API Usage

The application exposes a POST endpoint to query the database via natural language:

- **URL**: `http://localhost:5000/query`
- **Method**: POST
- **Content-Type**: `application/json`
- **Body**:
  ```json
  {
    "query": "Show me all records where the sales are above $5000"
  }
  ```

- **Response**:
  ```json
  {
    "result": "SELECT * FROM sales WHERE amount > 5000;"
  }
  ```

### Example Query

1. **Request**:
   ```bash
   curl -X POST http://localhost:5000/query \
   -H "Content-Type: application/json" \
   -d '{"query": "Show me all employees who joined after 2020"}'
   ```

2. **Response**:
   ```json
   {
     "result": [
       {
         "employee_id": 1,
         "name": "John Doe",
         "join_date": "2021-03-15"
       },
       {
         "employee_id": 2,
         "name": "Jane Smith",
         "join_date": "2022-05-20"
       }
     ]
   }
   ```

## Error Handling

If an invalid query is submitted or an error occurs, the API will return an appropriate error message:
- **400 Bad Request**: If no query is provided in the request.
- **500 Internal Server Error**: For any other errors during query execution.

Example error response:
```json
{
  "error": "No query provided"
}
```

## Future Improvements
- **Authentication**: Add user authentication and authorization for secure API access.
- **Enhanced Query Parsing**: Improve the natural language understanding to handle more complex queries.
- **Caching**: Implement query result caching for faster repeated queries.

