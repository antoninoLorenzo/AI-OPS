import React, {useEffect} from 'react';
import {Stack, TextField, Divider} from '@mui/material';
import {Role, Message} from './Message';


function MessageItem({message, isLast}) {
    return (
        <>
            <TextField
                variant="standard"
                defaultValue={message.content}
                sx={{
                    width: '100%',
                    padding: '8px 8px', 
                    input: { color: 'var(--white)'},
                    '& textarea': { 
                        color: 'var(--white)',
                    },
                }}
                InputProps={{
                    multiline: true,
                    readOnly: true,
                    disableUnderline: true,
                }}
            />
            {isLast ? undefined : <Divider sx={{border: '1px solid var(--light-grey)'}}/>}
        </>
    );
}

function MessageList({messageState}) {
    const [messages, setMessages] = messageState;

    useEffect(() => {
        renderMessages()
    }, [messages, setMessages]);

    const renderMessages = () => {
        return messages.map((msg, idx) => {
            return <MessageItem 
                key={idx} 
                message={msg} 
                isLast={idx < messages.length - 1 ? false : true}
            />
        });
    }

    return (
        <Stack
            spacing={2}
            sx={{
                width: '80%',
                height: '80vh',
                mt: '24px'
            }}
        >
            {renderMessages()}
        </Stack>
    );
}
 

export default MessageList;
