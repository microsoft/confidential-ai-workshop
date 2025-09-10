import os
import pandas as pd
import logging
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import xgboost as xgb
import skr_decrypt as skr

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def main():
    load_dotenv()
    logging.info("--- Starting Confidential XGBoost Training (In-Memory) ---")

    # 1. Securely unwrap the DEK inside the TEE
    logging.info("Attesting to Azure and unwrapping DEK...")
    dek = skr.unwrap_dek(
        os.environ["WRAPPED_KEY_FILE"],
        os.environ["ATTEST_URL"],
        os.environ["KEY_KID"]
    )
    logging.info("DEK securely retrieved.")

    # 2. Decrypt the dataset directly into memory
    encrypted_file = os.environ['ENC_FILE']
    logging.info(f"Decrypting '{encrypted_file}' into memory...")
    decrypted_stream = skr.decrypt_to_memory(encrypted_file, dek)
    del dek # The DEK is no longer needed, clear it from memory
    logging.info("Decryption complete.")

    # 3. Load data and train the model
    logging.info("Loading data into pandas and training model...")
    df = pd.read_csv(decrypted_stream)
    
    X = df.drop("Outcome", axis=1)
    y = df["Outcome"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(eval_metric='logloss')
    model.fit(X_train, y_train)
    logging.info("Model training finished.")

    # 4. Evaluate the model
    logging.info("Evaluating model performance...")
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    report = classification_report(y_test, preds)

    logging.info("--- Training Complete ---")
    logging.info(f"Model Accuracy: {acc:.4f}")
    # Log the multi-line classification report
    logging.info(f"Classification Report:\n{report}")

if __name__ == "__main__":
    main()