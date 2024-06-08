const Role = Object.freeze({
    USER: 'user',
    ASSISTANT: 'assistant'
});

class Message {
    constructor(role, content) {
        if (!Object.values(Role).includes(role))
            throw new Error('Invalid role for message.')

        this.role = role
        this.content = content
    }
}

export {Role, Message};