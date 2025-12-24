import ipsum

# Load the English language model
model = ipsum.load_model("en")

# Returns a list of 3 strings, each resembling a paragraph of English
paragraphs = model.generate_paragraphs(9)

print(paragraphs)