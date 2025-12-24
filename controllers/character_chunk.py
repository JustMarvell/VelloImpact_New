MAX_FIELD_LENGTH = 1024

def get_chunk(text: str) -> list:
    chunks = []
    current_chunk = ""

    lines = text.split('\n')
    
    for line in lines:
        if len(current_chunk) + len(line) + 1 <= MAX_FIELD_LENGTH:
            current_chunk += line + '\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line + '\n'

    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks
