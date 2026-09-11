import json

subsections = ["experience", "leadership", "projects"]

# Load the JSON
with open("exp.json", "r") as file:
    data = json.load(file)

# Add IDs
for subsection in subsections:
    for idx, entry in enumerate(data[subsection]):
        data[subsection][idx] = {"id": idx, **entry}

# Save the updated JSON
with open("exp.json", "w") as file:
    json.dump(data, file, indent=4)
