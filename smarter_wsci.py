from pathlib import Path
from ollama import chat
import json



question = """
I changed my university password this morning.
Now my Windows laptop won't connect to campus Wi-Fi,
but my phone still works.
"""

## WRITE ##
service_status = {
    "wifi": "operational"
}

state = {
    "problem": question,
    "service_status": service_status,
    "wifi_check": True
}

with open("state.json", "w") as file:
    json.dump(
        state,
        file,
        indent=2
    )

with open("state.json", "r") as file:
    state = json.load(file)

print(state)


## SELECT CONTEXT FILES BASED ON QUESTION
## Create the function that takes the student's question, takes some keywords and chooses the relevant files from the knowledge base. Return a list of the selected files.
## For example, if the question has the kyeword "print" or "printer", then the function should return the file "knowledge/printer_setup.txt" in a list.
def select_context(question):
    question_lower = question.lower()
    keyword_map = {
        "knowledge/wifi_setup.txt": [
            "wifi", "wi-fi", "wireless", "eduroam", "network", "connect"
        ],
        "knowledge/password_changes.txt": [
            "password", "changed", "credential"
        ],
        "knowledge/printing.txt": [
            "print", "printer"
        ],
        "knowledge/email_setup.txt": [
            "email", "mail"
        ],
        "knowledge/vpn.txt": [
            "vpn"
        ],
        "knowledge/classroom_projectors.txt": [
            "projector", "classroom", "display"
        ],
        "knowledge/service_status.txt": [
            "status", "operational", "outage", "down", "service"
        ],
    }
    selected = []
    for file_path, keywords in keyword_map.items():
        if any(keyword in question_lower for keyword in keywords):
            if file_path not in selected:
                selected.append(file_path)
    ## Always include service_status so the agent can rule out outages
    if "knowledge/service_status.txt" not in selected:
        selected.append("knowledge/service_status.txt")
    return selected


selected_files = select_context(question)
print("Selected files:", selected_files)

## READ SELECTED FILES and add their contents to the context variable.
context = ""
for file_path in selected_files:
    context += Path(file_path).read_text()
    context += "\n\n"


##
## COMPRESS CONTEXT
## Add logic to compress the context from above by calling Qwen with "context" and the "question" as the parameter
## The response from Qwen should be the compressed context. Store it in a variable called "compressed_context"

def compress_context(context, question):
    response = chat(
        model="qwen",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a context compression assistant. "
                    "Extract ONLY the information from the context that is "
                    "relevant to answering the question. "
                    "Discard every unrelated detail. "
                    "Return only the compressed, relevant context as plain text."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion:\n{question}",
            },
        ],
    )
    return response.message.content


compressed_context = compress_context(context, question)


## Print the length of the compressed context
print("Compressed context length:", len(compressed_context))

## Now, call Qwen again with the compressed context and the student's question. Store the response in a variable called "response" and print the response from Qwen.
## Ensure the model produces a structured output
response = chat(
    model="qwen",
    messages=[
        {
            "role": "system",
            "content": (
                "You are a university IT support assistant. "
                "Use the compressed context to answer the student's problem. "
                "Return your answer as JSON with keys: "
                '"diagnosis" (short statement of the problem), '
                '"cause" (likely cause), and '
                '"steps" (a list of actionable steps).'
            ),
        },
        {
            "role": "user",
            "content": f"Context:\n{compressed_context}\n\nQuestion:\n{question}",
        },
    ],
    format="json",
)


print(response.message.content)

## WRITE the above output in an artifact called "state"
try:
    diagnosis = json.loads(response.message.content)
except json.JSONDecodeError:
    diagnosis = {"raw_response": response.message.content}

state["diagnosis"] = diagnosis

with open("state.json", "w") as file:
    json.dump(state, file, indent=2)

print("State artifact written to state.json")

## Update the rest of the code so that it uses the "state" artifact as part of the context. 
## It is important to ensure that the model uses only the relevant parts from the "state" artifact and not the entire artifact.
## For this, you may have to think of a good structure for the "state" artifact and how to use it in the context.
##
## ISOLATE
## Create separate state artifacts for different agent tasks, then use Qwen
## to classify the problem so only the relevant artifact is used.
diagnostic_context = {
    "problem": state.get("problem", ""),
    "device": "Windows laptop",
    "wifi_status": state.get("service_status", {}).get("wifi", "unknown"),
    "diagnosis": state.get("diagnosis", {}),
}

report_context = {
    "total_wifi_cases": 37,
    "resolved_cases": 29,
    "unresolved_cases": 8,
}


def classify_task(question):
    """Use Qwen to classify the question and pick the right state artifact."""
    result = chat(
        model="qwen",
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify the user's question as either "
                    "'diagnostic' (troubleshooting a problem) or "
                    "'report' (statistics / summary). "
                    'Reply with only one word: "diagnostic" or "report".'
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ],
    )
    return result.message.content.strip().lower()


task_type = classify_task(question)
print("Classified task:", task_type)

## Select only the relevant state artifact based on the classification
if task_type == "report":
    relevant_state = report_context
else:
    relevant_state = diagnostic_context

## Final call: use only the relevant part of the state artifact + compressed context
final_response = chat(
    model="qwen",
    messages=[
        {
            "role": "system",
            "content": (
                "You are a university IT support assistant. "
                "Use the provided state artifact and compressed context "
                "to address the student's problem clearly and step by step."
            ),
        },
        {
            "role": "user",
            "content": (
                f"State artifact:\n{json.dumps(relevant_state, indent=2)}\n\n"
                f"Compressed context:\n{compressed_context}\n\n"
                f"Question:\n{question}"
            ),
        },
    ],
)

print(final_response.message.content)
