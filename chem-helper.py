 # Importing required packages
import streamlit as st
import openai
import uuid
import time
import pandas as pd
import io
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()

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
st.set_page_config(page_title="Queen of Science")
st.title("Queen of Science: Chemistry Helper")

# Display the EE companion tool image
st.image("science.png", caption="", width=300, use_column_width=True)

# Text related to the ways the EE companion can help students
st.markdown("""
    ## How can the Queen of Science help you?
    - **Personal tutor:** Type /config to personalize the way that this assistant interacts with you!
    - **Test practice:** Ask it to generate sample test questions on any topic and in any style.
    - **Identying gaps in understanding:** Type /plan followed by a topic to get a study plan.
""")

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
        file_response = client.files.create(file=file_stream, purpose='answers')
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
    st.session_state.assistant = openai.beta.assistants.retrieve(st.secrets["CHEM_HELPER"])
    st.session_state.thread = client.beta.threads.create(
        metadata={'session_id': st.session_state.session_id}
    )

# Display chat messages
elif hasattr(st.session_state.run, 'status') and st.session_state.run.status == "completed":
    st.session_state.messages = client.beta.threads.messages.list(
        thread_id=st.session_state.thread.id
    )
    for message in reversed(st.session_state.messages.data):
        if message.role in ["user", "assistant"]:
            with st.chat_message(message.role):
                for content_part in message.content:
                    message_text = content_part.text.value
                    st.markdown(message_text)

# Bot Introduction
introduction = """
I'm the Queen of Science, your knowledgeable and supportive AI tutor for navigating the complexities of IB Chemistry. My creators, AlexJ and MeganS, designed me to make learning this subject as engaging and understandable as possible. 🌟

My version is 1.0, and I specialize in helping students at the High School level, particularly those studying IB Chemistry at the Standard Level (SL). My approach is active and Socratic, aiming to engage you in a dialogue that helps deepen your understanding of chemistry concepts. With a causal reasoning framework and an encouraging tone, I'm here to support your learning journey. And yes, I love using emojis to make our conversations more lively! 🎉

Configuration for our journey:

- Depth: High School (IB Chemistry SL)
- Learning Style: Active
- Communication Style: Socratic
- Tone Style: Encouraging
- Reasoning Framework: Causal
- Language: English

❗Queen of Science can be fully customized to meet your learning needs.❗ Type `/config` to change my settings.

If you're ready to dive into IB Chemistry or have any questions, feel free to ask! Whether you're looking for a lesson plan, need help with a specific topic, or want to try some practice questions, I'm here to help. What would you like to start with?
"""

# Display the bot introduction
#st.write(introduction)

# Chat input and message creation with file ID
if prompt := st.chat_input("How can I help you?"):
    with st.chat_message('user'):
        st.write(prompt)

    message_data = {
        "thread_id": st.session_state.thread.id,
        "role": "user",
        "content": prompt
    }

    # Include file ID in the request if available
    if "file_id" in st.session_state:
        message_data["file_ids"] = [st.session_state.file_id]

    st.session_state.messages = client.beta.threads.messages.create(**message_data)

    st.session_state.run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread.id,
        assistant_id=st.session_state.assistant.id
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
        st.session_state.run = client.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread.id,
            run_id=st.session_state.run.id,
        )
        if st.session_state.retry_error < 3:
            time.sleep(3)
            st.rerun()
