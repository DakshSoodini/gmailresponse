from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

def load_local_model():
    model_id = "tiiuae/falcon-7b-instruct"  # Public, fast, and good for replies
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    generator = pipeline(
        "text-generation",
        model=model_id,
        tokenizer=tokenizer,
        device_map="auto",
        pad_token_id=tokenizer.eos_token_id
    )
    return generator
