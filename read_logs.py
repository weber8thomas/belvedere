import re 
import os

def parse_log(filename, pattern_progress, pattern_error):
    with open(filename, 'r') as f:
        for i, line in enumerate(f, start=1):  # Efficiently reads the file line-by-line
            match_progress = pattern_progress.match(line)
            match_error = pattern_error.match(line)
            
            if match_progress:
                yield ('success', i, line.strip(), int(match_progress.group(1)))
            elif match_error:
                yield ('error', i, line.strip())

path = "/Users/tweber/Gits/snakemake_logs_dev/.snakemake/log"
filename = os.path.join(path, os.listdir(path)[1])

# Pre-compiled regex patterns
pattern_progress = re.compile(r"\d+ of \d+ steps \((\d+)%\) done")
pattern_error = re.compile(r"Exiting because a job execution failed. Look above for error message")

last_success = None
last_error = None

for match_type, line_num, line, *rest in parse_log(filename, pattern_progress, pattern_error):
    if match_type == 'success':
        last_success = (line_num, line, rest[0])  # rest[0] contains the percentage for success
    else:
        last_error = (line_num, line)

if last_success:
    line_num, line, percentage = last_success
    print(f"Last match for success at line {line_num} ({percentage}% complete): {line}")

if last_error:
    line_num, line = last_error
    print(f"Last match for error at line {line_num}: {line}")
