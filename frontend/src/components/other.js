import '../css/shared.css';
import { API_URL } from '..';
import React, {useState, useEffect, useContext} from 'react';
import {Box, Divider, TextField, InputAdornment, IconButton, List, ListItem} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';

const promptBoxStyle = {
    width: '100%', 
    height: '12dvh', 
    display: 'flex', 
    justifyContent: 'center', 
    alignItems: 'center', 
    position: 'absolute', 
    bottom: '0'
}

const promptTextFieldStyle = {
    width: '60%',
    backgroundColor: 'var(--white)',
    color: 'var(--white)',
    borderRadius: '12px',
};


/**
 * Makes a request to API_URL/query and puts each chunk into messages list 
 * @param userInput: the encoded input string
 */
function makeQuery(userInput, setMessages) {
    const url = `${API_URL}/query?user_input=${userInput}`;
        
    fetch(url)
    .then(response => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        const readStream = async () => {
            let result = await reader.read();
            
            // Add new empty message
            let text = ''
            setMessages(prevMessages => [...prevMessages, text])
            while (!result.done) {
                text += decoder.decode(result.value);

                // Update last message with chunks
                setMessages(prevMessages => {
                    const newMessages = [...prevMessages];
                    newMessages[newMessages.length - 1] = text;
                    return newMessages;
                });                
                
                result = await reader.read();
            }
        };
    
        readStream().catch(console.error);          
    })
    .catch(error => console.log(error))
}

/**
 * The text field where user types in.
 */
function PromptField() {
    const { setMessages } = useContext(MessageContext);
    const [inputValue, setInputValue] = useState('');

    const inputHandler = () => {       
        setMessages(prevMessages => [...prevMessages, inputValue]);
        makeQuery(
            encodeURIComponent(inputValue), 
            setMessages
        );
        setInputValue('');
    }

    return (
        <Box sx={promptBoxStyle}>
            <TextField
                variant="outlined"
                placeholder='Type Something'
                multiline
                sx={promptTextFieldStyle}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                InputProps={{
                    endAdornment: (
                        <InputAdornment position='end'>
                            <IconButton>
                                <SendIcon />
                            </IconButton>
                        </InputAdornment>
                    ),
                }}
            />
        </Box>
    );
};

