const TaskStatus = Object.freeze({
    WAITING: 0,
    RUNNING: 1,
    DONE: -1,
});

class Task {
    constructor(name) {
        this.name = name;
        this.taskStatus = TaskStatus.WAITING;
    }

    setStatus(status) {
        if (Object.values(TaskStatus).includes(status)) 
            this.taskStatus = status;
        else 
            throw new Error('Invalid task status');
    }

    getStatusName() {
        if (this.taskStatus == TaskStatus.DONE) return "Done";
        else if (this.taskStatus == TaskStatus.RUNNING) return "Running";
        else if (this.taskStatus == TaskStatus.WAITING) return "Scheduled";
    }
}

export {Task, TaskStatus};