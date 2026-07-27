from openai import OpenAI
import traceback

client = OpenAI()

print("AI chatbot started. Type quit to exit.")

while True:
    question = input("You: ")

    if question.lower() == "quit":
        break

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=question
        )

        print("AI:", response.output_text)

    except Exception:
        traceback.print_exc()