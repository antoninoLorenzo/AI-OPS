import '../css/shared.css';
import React, { useState } from 'react';
import { Grid } from '@mui/material';
import {Role, Message} from './chat/Message';
import MessageList from './chat/MessageList';
import PromptField from './chat/PromptField';


const chatBoxStyle = { 
    bgcolor: 'var(--grey)', 
    width: '80vw',
    height: '100vh',
    display: 'flex', 
    flexDirection: 'column', 
    justifyContent: 'start',
    alignItems: 'center'

}


export default function ChatBox() {
    const [messages, setMessages] = useState([])

    const addUserMessage = (msg) => { setMessages([...messages, new Message(Role.USER, msg)]); }

    return (
        <Grid item sx={chatBoxStyle}>
            <MessageList messageState={[messages, setMessages]}/>
            <PromptField addMessage={addUserMessage}/>
        </Grid>
    );
}
