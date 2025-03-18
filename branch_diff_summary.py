import subprocess
import os
import sys

def run_command(command):
    """Run a shell command and return the output"""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def get_current_branch():
    """Get the name of the current branch"""
    return run_command("git branch --show-current")

def get_changed_files():
    """Get list of changed files between branches"""
    return run_command("git diff novas_implementaçoes --name-status").split("\n")

def get_file_diff(file_path):
    """Get diff for a specific file"""
    if os.path.exists(file_path):
        return run_command(f"git diff novas_implementaçoes -- {file_path}")
    return "File does not exist in current branch"

def main():
    current_branch = get_current_branch()
    print(f"Current branch: {current_branch}")
    print(f"Comparing with branch: novas_implementaçoes\n")
    
    changed_files = get_changed_files()
    if not changed_files or changed_files[0] == '':
        print("No differences found between branches.")
        return
    
    print(f"Found {len(changed_files)} changed files:\n")
    
    for change in changed_files:
        if not change.strip():
            continue
            
        parts = change.split()
        change_type = parts[0]
        file_path = parts[1] if len(parts) > 1 else "Unknown file"
        
        type_desc = {
            'A': "Added in novas_implementaçoes",
            'M': "Modified",
            'D': "Deleted in novas_implementaçoes"
        }.get(change_type, "Unknown change")
        
        print(f"{file_path} - {type_desc}")
        
        # Only show diff for modified files that exist
        if change_type == 'M' and os.path.exists(file_path):
            print("\nSummary of changes:")
            diff = get_file_diff(file_path)
            # Print a simplified diff - just first few lines
            diff_lines = diff.split("\n")[:10]  # First 10 lines
            for line in diff_lines:
                if line.startswith("+") and not line.startswith("+++"):
                    print(f"  Added: {line[1:]}")
                elif line.startswith("-") and not line.startswith("---"):
                    print(f"  Removed: {line[1:]}")
            if len(diff.split("\n")) > 10:
                print("  (more changes not shown...)")
            print()

if __name__ == "__main__":
    main()
