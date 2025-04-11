import os
import tempfile

TODO_FILE = "todo.txt"

def load_tasks():
    if not os.path.exists(TODO_FILE):
        return []
    tasks = []
    with open(TODO_FILE, "r") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) == 3:
                task, status, due = parts
                tasks.append({"task": task, "done": status == "done", "due": due})
    return tasks

def save_tasks(tasks):
    # Write securely to a temp file then rename
    fd, temp_path = tempfile.mkstemp()
    with os.fdopen(fd, "w") as f:
        for t in tasks:
            line = f"{t['task']}|{'done' if t['done'] else 'pending'}|{t['due']}\n"
            f.write(line)
    os.replace(temp_path, TODO_FILE)

def show_tasks(tasks):
    if not tasks:
        print("✅ No pending tasks!")
        return
    print("\n📋 Your To-Do List:")
    for i, t in enumerate(tasks, 1):
        status = "✅" if t['done'] else "❌"
        due = f"(Due: {t['due']})" if t['due'] else ""
        print(f"{i}. {status} {t['task']} {due}")

def add_task(tasks):
    task = input("🆕 Enter new task: ").strip()
    due = input("📅 Enter due date (optional): ").strip()
    if task:
        tasks.append({"task": task, "done": False, "due": due})
        save_tasks(tasks)
        print("✅ Task added.")

def delete_task(tasks):
    show_tasks(tasks)
    try:
        idx = int(input("🗑️ Enter task number to delete: "))
        if 1 <= idx <= len(tasks):
            removed = tasks.pop(idx - 1)
            save_tasks(tasks)
            print(f"🗑️ Removed: {removed['task']}")
        else:
            print("❌ Invalid task number.")
    except ValueError:
        print("❌ Please enter a valid number.")

def mark_done(tasks):
    show_tasks(tasks)
    try:
        idx = int(input("☑️ Enter task number to mark as complete: "))
        if 1 <= idx <= len(tasks):
            tasks[idx - 1]['done'] = True
            save_tasks(tasks)
            print(f"✅ Marked as done: {tasks[idx - 1]['task']}")
        else:
            print("❌ Invalid task number.")
    except ValueError:
        print("❌ Please enter a valid number.")

def edit_task(tasks):
    show_tasks(tasks)
    try:
        idx = int(input("✏️ Enter task number to edit: "))
        if 1 <= idx <= len(tasks):
            new_text = input("🔤 New task text (leave blank to keep unchanged): ").strip()
            new_due = input("📅 New due date (leave blank to keep unchanged): ").strip()
            if new_text:
                tasks[idx - 1]['task'] = new_text
            if new_due:
                tasks[idx - 1]['due'] = new_due
            save_tasks(tasks)
            print("✅ Task updated.")
        else:
            print("❌ Invalid task number.")
    except ValueError:
        print("❌ Please enter a valid number.")

def main():
    while True:
        print("\n--- 📝 To-Do App ---")
        print("1. Show Tasks")
        print("2. Add Task")
        print("3. Delete Task")
        print("4. Mark Task as Done")
        print("5. Edit Task")
        print("6. Exit")
        choice = input("Choose an option: ").strip()

        tasks = load_tasks()

        if choice == "1":
            show_tasks(tasks)
        elif choice == "2":
            add_task(tasks)
        elif choice == "3":
            delete_task(tasks)
        elif choice == "4":
            mark_done(tasks)
        elif choice == "5":
            edit_task(tasks)
        elif choice == "6":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Try again.")






if __name__ == "__main__":
    main()
