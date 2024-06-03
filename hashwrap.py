import subprocess
import json
import argparse
import os
import sys
import time
import threading
from datetime import datetime

def check_files_exist(files):
    """
    Check if the given files exist.

    :param files: List of file paths to check.
    :return: True if all files exist, False otherwise.
    """
    missing_files = [file for file in files if not os.path.isfile(file)]
    if missing_files:
        print(f"Error: The following files are missing: {', '.join(missing_files)}")
        return False
    return True

def count_cracked_hashes(potfile):
    """
    Count the number of cracked hashes in the given potfile.

    :param potfile: Path to the potfile.
    :return: Number of cracked hashes.
    """
    if not os.path.isfile(potfile):
        return 0
    with open(potfile, 'r') as f:
        return len(f.readlines())

def monitor_potfile(potfile, initial_count):
    """
    Monitor the potfile for new entries and print them.

    :param potfile: Path to the potfile.
    :param initial_count: Initial number of entries in the potfile.
    """
    while True:
        with open(potfile, 'r') as f:
            current_lines = f.readlines()

        new_lines = current_lines[initial_count:]
        for line in new_lines:
            print(f"\033[38;5;208m*** SUCCESSFULLY CRACKED HASH ***\033[0m")
            print(f"\033[38;5;208m{line.strip()}\033[0m")
            print(f"\033[38;5;208m*** SUCCESSFULLY CRACKED HASH ***\033[0m\n")

        initial_count = len(current_lines)
        time.sleep(1)

def periodic_message(interval):
    """
    Print a periodic message to indicate that the script is still running.

    :param interval: Time in seconds to wait between messages.
    """
    while True:
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"Cracking hashes... {current_time_str}")
        time.sleep(interval)

def run_hashcat(config_file, hashcat_args):
    """
    Run Hashcat with configurations from a JSON file and additional command line arguments.

    :param config_file: Path to the JSON configuration file.
    :param hashcat_args: List of command line arguments for Hashcat.
    """
    # Ensure the script is run with sudo
    if os.geteuid() != 0:
        print("This script must be run with sudo.")
        sys.exit(1)

    # Load configuration from JSON file
    with open(config_file, 'r') as f:
        config = json.load(f)

    hash_file = config["hash_file"]
    potfile = config.get("potfile", "hashcat.potfile")
    hashcat_path = config.get("hashcat_path", "hashcat")
    combinations = config["combinations"]
    message_interval = config.get("message_interval", 10)  # Default to 10 seconds if not specified

    # Check if the hash file exists
    if not os.path.isfile(hash_file):
        print(f"Error: Hash file '{hash_file}' not found.")
        return

    # Check if all wordlists and rulesets exist
    files_to_check = [hash_file]
    for combo in combinations:
        files_to_check.append(combo["wordlist"])
        if combo.get("ruleset"):
            files_to_check.append(combo["ruleset"])

    if not check_files_exist(files_to_check):
        return

    # Create the potfile if it doesn't exist
    if not os.path.isfile(potfile):
        open(potfile, 'w').close()

    # Monitor the potfile for new entries
    initial_cracked_hashes = count_cracked_hashes(potfile)
    potfile_monitor_thread = threading.Thread(target=monitor_potfile, args=(potfile, initial_cracked_hashes))
    potfile_monitor_thread.daemon = True
    potfile_monitor_thread.start()

    # Start the periodic message thread
    message_thread = threading.Thread(target=periodic_message, args=(message_interval,))
    message_thread.daemon = True
    message_thread.start()

    for combo in combinations:
        wordlist = combo["wordlist"]
        ruleset = combo.get("ruleset")
        cmd = [
            hashcat_path,
            hash_file,                 # Hash file
            wordlist,                  # Wordlist file
            "--potfile-path", potfile, # Potfile path
            "--quiet"                  # Suppress normal output
        ]
        if ruleset:
            cmd.extend(["--rules-file", ruleset])  # Add ruleset if provided

        cmd.extend(hashcat_args)  # Append additional arguments

        start_time = datetime.now()
        start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"\033[92m### Starting: Wordlist {wordlist} with Ruleset {ruleset if ruleset else 'None'} | Start: {start_time_str} ###\033[0m")

        # Start the Hashcat process interactively
        process = subprocess.Popen(cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=subprocess.PIPE)

        # Wait for the Hashcat process to complete
        process.wait()

        end_time = datetime.now()
        end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        duration = end_time - start_time
        duration_str = str(duration)

        if process.returncode == 0:
            print(f"\033[94m### Completed: Wordlist {wordlist} with Ruleset {ruleset if ruleset else 'None'} | Finished: {end_time_str} | Time Ran: {duration_str} ###\033[0m")
        else:
            print(f"\033[91m### Error: Wordlist {wordlist} with Ruleset {ruleset if ruleset else 'None'} ###\033[0m")
            if process.stderr:
                stderr_output = process.stderr.read().decode()
                print(stderr_output)
            else:
                print("No error output")

    print(f"All Wordlists/Rules completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hashcat Wrapper Script")
    parser.add_argument("config_file", help="Path to the JSON configuration file")
    parser.add_argument("hashcat_args", nargs=argparse.REMAINDER, help="Arguments to pass to Hashcat (including -m, -a, etc.)")

    args = parser.parse_args()

    run_hashcat(args.config_file, args.hashcat_args)
