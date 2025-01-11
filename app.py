import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groclake.vectorlake import VectorLake
from groclake.modellake import ModelLake

# FastAPI App
app = FastAPI()

# Set API key and account ID
GROCLAKE_API_KEY = '92cc227532d17e56e07902b254dfad10'
GROCLAKE_ACCOUNT_ID = 'e1704d8c9480eb7c49ee0d6dc660f47d'

# Set environment variables
os.environ["GROCLAKE_API_KEY"] = GROCLAKE_API_KEY
os.environ["GROCLAKE_ACCOUNT_ID"] = GROCLAKE_ACCOUNT_ID

# Initialize components
vectorlake = VectorLake()
modellake = ModelLake()

# Global variable to store vectorlake_id
vectorlake_id = None


class ChatRequest(BaseModel):
    query: str


@app.post("/chat")
async def chat(request: ChatRequest):
    """Chat endpoint for processing user queries."""
    try:
        # Step 1: Get user query from request
        query = request.query
        if not query:
            raise HTTPException(status_code=400, detail="Query is required.")

        # Step 2: Generate vector for the user query
        vector_search_data = vectorlake.generate(query)
        search_vector = vector_search_data.get("vector")

        # Step 3: Search VectorLake
        search_payload = {
            "vector": search_vector,
            "vectorlake_id": vectorlake_id,
            "vector_type": "text",
        }
        search_response = vectorlake.search(search_payload)
        
        # Print the search response for debugging
        print("Search Response:", search_response)

        search_results = search_response.get("results", [])
        
        # Step 4: Construct enriched context
        enriched_context = " ".join([result.get("vector_document", "") for result in search_results])

        # Step 5: Query ModelLake with enriched context
        payload = {
            "messages": [
                {"role": "system", "content": "You are an HR assistant providing accurate office-related guidance."},
                {
                    "role": "user",
                    "content": f"Using the following context: {enriched_context}, "
                               f"answer the question: {query}."
                }
            ]
        }
        chat_response = modellake.chat_complete(payload)
        answer = chat_response.get("answer", "No answer received.")
        return {"answer": answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)
