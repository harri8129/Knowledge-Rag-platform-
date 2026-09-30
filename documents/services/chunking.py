def split_text(text: str,chunk_size : int = 500,chunk_overlap: int = 100):
    """
    Splits the text into overlapping chunks.

    Offsets refer to the original text string 
    Each yielded tuple is (content, start_offset , end_offset).
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be >= 0 and < chunk_size."
        )

    text_lenght = len(text)
    start = 0 

    while start < text_lenght:
        
        # Skip whitespace at the start of the chunk 
        while start < text_lenght and text[start].isspace():
            start += 1
        if start >= text_lenght:
            break
        
        end = min(start + chunk_size, text_lenght)

        if end < text_lenght:
            # look for a whitespace boundary in the latter half 
            # of the proposed chunk 
            minimum_end = start + chunk_size // 2
            boundary = text.rfind(" ", minimum_end , end)
            
            if boundary == -1:
                boundary = text.rfind("\n", minimum_end , end)

            if boundary > start:
                end = boundary

        content = text[start:end].strip()


        if content:
            #Account for whitespace stripped from either edge.
            actual_start = start 
            while actual_start < end and text[actual_start].isspace():
                actual_start += 1

            actual_end = end 
            while actual_end > actual_start and text[actual_end - 1].isspace():
                actual_end -= 1

            yield  content, actual_start,actual_end

        if end >= text_lenght:
            break

        #Move forward while retaining some context 
        next_start = max(start + 1, end - chunk_overlap)

        # Prevent overlap from repeatedly starting in whitespace.
        start = next_start            