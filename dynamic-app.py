 # Importing required packages
import streamlit as st
import openai
import uuid
import time
import pandas as pd
import io
import requests
from openai import OpenAI

# Initialize OpenAI client
#client = OpenAI()

# Your chosen model
#MODEL = "gpt-3.5-turbo-16k" # Legacy
#MODEL = "gpt-3.5-turbo-1106" # Latest model
MODEL = "gpt-4-1106-preview"

# Initialize session state variables
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "run" not in st.session_state:
    st.session_state.run = {"status": None}

if "messages" not in st.session_state:
    st.session_state.messages = []

if "retry_error" not in st.session_state:
    st.session_state.retry_error = 0

# Set up the page
st.set_page_config(page_title="Extended Essay Companion Tool")
st.title("EE Companion Tool")

# Display the EE companion tool image
st.image("companion.png", caption="Your Extended Essay Companion")

# Text related to the ways the EE companion can help students
st.markdown("""
    ## How can the EE Companion assist you?
    - **Choosing a subject:** The EE Companion can provide insights into how to select the best subject based on your interests and academic strengths.
    - **Narrowing down the topic:** It can help refine your broad interests into a specific, researchable topic.
    - **Formulating a research question:** The tool can guide you towards crafting a focused, clear, and engaging research question.
    - **Planning:** Offering advice on planning your research, structuring your essay, and managing your time effectively.
""")

# Add input fields for the OpenAI API Key and the Assistant's API Key
openai_api_key = st.sidebar.text_input("Enter your OpenAI API Key", type="password")
assistant_api_key = st.sidebar.text_input("Enter your Assistant's API Key", type="password")

# Function to initialize or update the OpenAI client and assistant with the provided API keys
def update_openai_client(openai_api_key, assistant_api_key):
    openai.api_key = openai_api_key
    # Assuming assistant_api_key is used for a custom purpose, like fetching a specific assistant configuration
    # Adjust the implementation based on your actual use case
    if assistant_api_key:  # Example condition, replace with actual logic if needed
        # Example of dynamically setting the assistant, adjust based on actual usage
        st.session_state.assistant = openai.beta.assistants.retrieve(assistant_id=assistant_api_key)
        # Example of creating a thread with dynamic session id
        st.session_state.thread = openai.beta.threads.create(
        metadata={'session_id': st.session_state.session_id}
    )

def search_core_entities(entity_type, query, limit=10, offset=0, stats=False, api_key=st.secrets["CORE_API"]):
    api_endpoint = f"https://api.core.ac.uk/v3/search/{entity_type}"
    headers = {'Authorization': f'Bearer {api_key}'}
    # Ensure 'fields' parameter requests all needed information
    params = {
        'q': query,
        'limit': limit,
        'offset': offset,
        'stats': stats,
        'fields': 'title,authors,publishedDate,sourceFulltextUrls,description'  # Adjust based on actual API field names
    }
    print(params)
    response = requests.get(api_endpoint, headers=headers, params=params)
    if response.status_code == 200:
        articles = response.json().get('results', [])
        return articles
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return []


# Button to trigger the update function
if st.sidebar.button("Update API Keys"):
    if openai_api_key and assistant_api_key:  # Ensure both keys are provided before updating
        update_openai_client(openai_api_key, assistant_api_key)
        st.sidebar.success("API Keys updated successfully!")
    else:
        st.sidebar.error("Please enter both API keys.")

# File uploader for CSV, XLS, XLSX
uploaded_file = st.file_uploader("Upload your file", type=["csv", "xls", "xlsx"])


if uploaded_file is not None:
    # Determine the file type
    file_type = uploaded_file.type

    try:
        # Read the file into a Pandas DataFrame
        if file_type == "text/csv":
            df = pd.read_csv(uploaded_file)
        elif file_type in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
            df = pd.read_excel(uploaded_file)

        # Convert DataFrame to JSON
        json_str = df.to_json(orient='records', indent=4)
        file_stream = io.BytesIO(json_str.encode())

        # Upload JSON data to OpenAI and store the file ID
        file_response = openai.files.create(file=file_stream, purpose='answers')
        st.session_state.file_id = file_response.id
        st.success("File uploaded successfully to OpenAI!")

        # Optional: Display and Download JSON
        st.text_area("JSON Output", json_str, height=300)
        st.download_button(label="Download JSON", data=json_str, file_name="converted.json", mime="application/json")
    
    except Exception as e:
        st.error(f"An error occurred: {e}")

# Initialize OpenAI assistant
if "assistant" not in st.session_state:
    openai.api_key = st.secrets["OPENAI_API_KEY"]
    st.session_state.assistant = openai.beta.assistants.retrieve(st.secrets["OPENAI_ASSISTANT"])
    st.session_state.thread = openai.beta.threads.create(
        metadata={'session_id': st.session_state.session_id}
    )

# Display chat messages
elif hasattr(st.session_state.run, 'status') and st.session_state.run.status == "completed":
    st.session_state.messages = openai.beta.threads.messages.list(
        thread_id=st.session_state.thread.id
    )
    for message in reversed(st.session_state.messages.data):
        if message.role in ["user", "assistant"]:
            with st.chat_message(message.role):
                for content_part in message.content:
                    message_text = content_part.text.value
                    st.markdown(message_text)

def is_search_query(prompt):
    ai_prompt = (f"Please analyze whether the following user input is specifically asking for academic articles "
                 f"from a database and not a general support question related to the IB Extended Essay. If it is a request for articles, identify that it is a search query"
                 f"and extract the key search terms. Otherwise, indicate it's not a search query")

    completion = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": ai_prompt},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200,
    )

    print(completion.choices[0].message.content)
    # Assuming the last message in the completion will be the AI's response
    response_message = completion.choices[0].message.content  # Access the content attribute directly

    # Adjust this to correctly identify the start of the key terms list in the response
    search_terms_start_phrase = "terms are:"
    search_terms_lines = response_message.split('\n')
    search_terms = []
    print(search_terms_lines)
    extracting = False
    for line in search_terms_lines:
        print(line)
        line = line.strip()
        print(line)
        if extracting and line.startswith("-"):
            term = line.strip('- ').strip()
            if term:  # Ensure the line isn't empty
                search_terms.append(term)
        elif search_terms_start_phrase.lower() in line.lower():
            extracting = True  # Start extracting terms from the next line
    
    if search_terms:
        # Concatenate extracted terms with "OR" for broader searches, or "AND" for more specific searches
        formatted_search_terms = " OR ".join(search_terms)
        print("Extracted search terms:", formatted_search_terms)
        return True, formatted_search_terms
    else:
        print("No search terms were extracted.")
        return False, None

def handle_search_query(search_terms):
    # Call the search function with the extracted terms
    results = search_core_entities("works", search_terms, limit=5)  # Adjust the limit as needed
    return results

def format_article(article):
    title = article.get('title', 'N/A')
    authors = ", ".join([author.get('name', 'N/A') for author in article.get('authors', [])])
    published_date = article.get('publishedDate', 'N/A')
    urls = article.get('sourceFulltextUrls', ['N/A'])[0]
    abstract = article.get('abstract', 'N/A')

    # Cap the abstract length to 150 characters
    if len(abstract) > 250:
        abstract = abstract[:250] + '...'

    # Use Markdown formatting for better readability
    formatted_str = f"**Title:** {title}\n" \
                    f"**Authors:** {authors}\n" \
                    f"**Published Date:** {published_date}\n" \
                    f"**URL:** [Link]({urls})\n" \
                    f"**Abstract:** {abstract}"
    return formatted_str


# Chat input and message creation with file ID
if prompt := st.chat_input("How can I help you?"):
    with st.chat_message('user'):
        st.write(prompt)

    is_search, search_terms = is_search_query(prompt)
    if is_search:
        # Use the extracted search terms to perform the search
        results = search_core_entities("works", search_terms, limit=5)
        if results:
            response = "\n\n".join([format_article(article) for article in results])
            st.write(response)
        else:
            st.write("No articles found. Please try a different query.")
    else:
        # Proceed with sending the prompt to the OpenAI API as before
        message_data = {
            "thread_id": st.session_state.thread.id,
            "role": "user",
            "content": prompt
        }

        # Include file ID in the request if available
        if "file_id" in st.session_state:
            message_data["file_ids"] = [st.session_state.file_id]

        st.session_state.messages = openai.beta.threads.messages.create(**message_data)

        st.session_state.run = openai.beta.threads.runs.create(
            thread_id=st.session_state.thread.id,
            assistant_id=st.session_state.assistant.id,
        )
        if st.session_state.retry_error < 3:
            time.sleep(1)
            st.rerun()

# Handle run status
if hasattr(st.session_state.run, 'status'):
    if st.session_state.run.status == "running":
        with st.chat_message('assistant'):
            st.write("Thinking ......")
        if st.session_state.retry_error < 3:
            time.sleep(1)
            st.rerun()

    elif st.session_state.run.status == "failed":
        st.session_state.retry_error += 1
        with st.chat_message('assistant'):
            if st.session_state.retry_error < 3:
                st.write("Run failed, retrying ......")
                time.sleep(3)
                st.rerun()
            else:
                st.error("FAILED: The OpenAI API is currently processing too many requests. Please try again later ......")

    elif st.session_state.run.status != "completed":
        st.session_state.run = openai.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread.id,
            run_id=st.session_state.run.id,
        )
        if st.session_state.retry_error < 3:
            time.sleep(3)
            st.rerun()
