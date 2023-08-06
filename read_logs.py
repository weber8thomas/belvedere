import re 

with open('logs_mosaicatcher/selected_logs/{log_file}', 'r') as f:
    log_content = f.read()

# Regular expression pattern
pattern = re.compile(r"\d+ of \d+ steps \(\d+%\) done")

# Split the log into lines
log_lines = log_content.strip().split('\n')

# Extract lines that match the pattern
extracted_lines = [line for line in log_lines if pattern.match(line)]

# Print the extracted lines
for line in extracted_lines:
    print(line)