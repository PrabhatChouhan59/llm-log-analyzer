"""
ollama_client.py - Ollama LLM API Client
------------------------------------------
Ollama is a tool that runs AI models locally (no internet needed!).
This file handles all communication with the Ollama server.

What is Ollama?
  - It's a server that runs open-source AI language models (like Llama, Mistral)
  - You send it a text prompt, it returns an AI-generated response
  - In Kubernetes, Ollama runs as a separate pod/service

How we use it:
  1. We POST a request to Ollama's /api/generate endpoint
  2. Ollama processes the prompt using the AI model
  3. We get back an AI-generated analysis of our logs
"""

import requests
import json
import logging
import os
import time

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    A client class for talking to the Ollama AI server.
    
    Think of this like a "translator" that helps your Python code
    communicate with the AI model running in Ollama.
    """

    def __init__(self):
        # Read the Ollama server URL from environment variable
        # In Kubernetes, this will be the service name: http://ollama-service:11434
        # Locally, it defaults to localhost
        self.base_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

        # The AI model to use (mistral is small and fast, good for analysis)
        self.model = os.getenv("OLLAMA_MODEL", "mistral")

        # How long to wait for the AI to respond (AI can be slow!)
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "120"))

        logger.info(f"OllamaClient initialized: url={self.base_url}, model={self.model}")

    def is_available(self) -> bool:
        """
        Check if Ollama server is running and accessible.
        Returns True if reachable, False otherwise.
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def ensure_model_pulled(self) -> bool:
        """
        Make sure the AI model is downloaded in Ollama.
        If not downloaded, this pulls (downloads) it.
        
        Returns True if model is ready, False if failed.
        """
        logger.info(f"Checking if model '{self.model}' is available in Ollama...")
        try:
            # Check what models are already downloaded
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                available_models = [m["name"] for m in response.json().get("models", [])]
                
                # Check if our model is already there
                model_ready = any(self.model in m for m in available_models)
                if model_ready:
                    logger.info(f"Model '{self.model}' is already available!")
                    return True
                
                # Pull (download) the model if not present
                logger.info(f"Pulling model '{self.model}' from Ollama... (this may take several minutes)")
                pull_response = requests.post(
                    f"{self.base_url}/api/pull",
                    json={"name": self.model},
                    timeout=600  # 10 minutes for large model downloads
                )
                
                if pull_response.status_code == 200:
                    logger.info(f"Model '{self.model}' pulled successfully!")
                    return True
                else:
                    logger.error(f"Failed to pull model: {pull_response.text}")
                    return False

        except requests.RequestException as e:
            logger.error(f"Failed to reach Ollama server: {e}")
            return False

    def generate(self, prompt: str) -> str:
        """
        Send a prompt to the AI model and get a response.
        
        Args:
            prompt: The text input to send to the AI (our log analysis request)
            
        Returns:
            The AI's response as a string, or an error message.
        """
        logger.info(f"Sending prompt to Ollama (model={self.model})...")
        
        try:
            # Build the request payload
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,    # Wait for full response (not streaming)
                "options": {
                    "temperature": 0.3,    # Lower = more focused/consistent output
                    "top_p": 0.9,
                    "max_tokens": 1500,    # Limit response length
                }
            }

            # Make the HTTP POST request to Ollama
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            elapsed = round(time.time() - start_time, 2)

            # Raise an exception if HTTP status code indicates an error
            response.raise_for_status()

            # Parse the JSON response
            result = response.json()
            ai_response = result.get("response", "").strip()

            logger.info(f"Ollama responded in {elapsed}s ({len(ai_response)} chars)")
            return ai_response

        except requests.Timeout:
            error_msg = f"Ollama timed out after {self.timeout}s. Try a smaller model."
            logger.error(error_msg)
            return f"ERROR: {error_msg}"

        except requests.ConnectionError:
            error_msg = f"Cannot connect to Ollama at {self.base_url}. Is it running?"
            logger.error(error_msg)
            return f"ERROR: {error_msg}"

        except requests.HTTPError as e:
            error_msg = f"Ollama returned HTTP error: {e}"
            logger.error(error_msg)
            return f"ERROR: {error_msg}"

        except (json.JSONDecodeError, KeyError) as e:
            error_msg = f"Failed to parse Ollama response: {e}"
            logger.error(error_msg)
            return f"ERROR: {error_msg}"

    def generate_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        """
        Like generate(), but retries up to max_retries times on failure.
        Good for handling temporary network hiccups.
        """
        for attempt in range(1, max_retries + 1):
            result = self.generate(prompt)
            
            if not result.startswith("ERROR:"):
                return result
            
            if attempt < max_retries:
                wait_time = attempt * 5  # Wait 5s, then 10s, then 15s
                logger.warning(f"Attempt {attempt} failed. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        logger.error(f"All {max_retries} attempts failed.")
        return result  # Return last error message
