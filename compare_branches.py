import os

def compare_branches():
    # Checkout to the simplificando branch
    os.system('git checkout simplificando')
    
    # Fetch the latest changes from the remote repository
    os.system('git fetch origin')
    
    # Compare with the main branch and save the output to a file
    os.system('git diff origin/main > branch_diff.txt')
    
    print("Comparison complete. Differences saved in branch_diff.txt")

def compare_branches_simplificado():
    os.system('git checkout simplificando')
    os.system('git fetch origin')
    os.system('git diff origin/main > branch_diff_simplificado.txt')
    print("Differences for 'simplificando' saved in branch_diff_simplificado.txt")

if __name__ == "__main__":
    compare_branches()
