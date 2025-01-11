import os
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from groclake.vectorlake import VectorLake
from groclake.datalake import DataLake
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
datalake = DataLake()
modellake = ModelLake()

# Global variables to store IDs
datalake_id = None
vectorlake_id = None


class DocumentRequest(BaseModel):
    document_url: str


class ChatRequest(BaseModel):
    query: str


@app.post("/upload_document")
async def upload_document(request: DocumentRequest):
    """Upload a document to DataLake and process it for VectorLake."""
    global datalake_id, vectorlake_id

    try:
        # Step 1: Create DataLake and VectorLake if not already created
        if not datalake_id:
            datalake_create = datalake.create()
            if "datalake_id" in datalake_create:
                datalake_id = datalake_create["datalake_id"]
                print(f"DataLake created with ID: {datalake_id}")
            else:
                print(f"Error creating DataLake: {datalake_create}")
                raise HTTPException(status_code=500, detail="Failed to create DataLake")
        
        if not vectorlake_id:
            vector_create = vectorlake.create()
            if "vectorlake_id" in vector_create:
                vectorlake_id = vector_create["vectorlake_id"]
                print(f"VectorLake created with ID: {vectorlake_id}")
            else:
                print(f"Error creating VectorLake: {vector_create}")
                raise HTTPException(status_code=500, detail="Failed to create VectorLake")

        # Step 2: Get document URL from request
        document_url = request.document_url
        if not document_url:
            raise HTTPException(status_code=400, detail="Document URL is required.")

        # Step 3: Push the document to DataLake
        payload_push = {
            "datalake_id": datalake_id,
            "document_type": "url",
            "document_data": document_url
        }
        data_push = datalake.push(payload_push)
        document_id = data_push.get("document_id")
        if not document_id:
            raise HTTPException(status_code=500, detail="Failed to push document.")

        print(f"Document pushed successfully with ID: {document_id}")

        # Step 4: Fetch and process the document
        payload_fetch = {
            "document_id": document_id,
            "datalake_id": datalake_id,
            "fetch_format": "chunk",
            "chunk_size": "500"
        }
        data_fetch = datalake.fetch(payload_fetch)
        document_chunks = data_fetch.get("document_data", [])
        print(f"Document fetched successfully. Total chunks: {len(document_chunks)}")

        # Step 5: Push chunks to VectorLake
        for chunk in document_chunks:
            vector_doc = vectorlake.generate(chunk)
            vector_chunk = vector_doc.get("vector")
            vectorlake_push_request = {
                "vector": vector_chunk,
                "vectorlake_id": vectorlake_id,
                "document_text": chunk,
                "vector_type": "text",
                "metadata": {}
            }
            vectorlake.push(vectorlake_push_request)

        return {"message": "Document processed successfully!"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
