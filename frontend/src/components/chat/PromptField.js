import React, { useState } from 'react';
import { TextField, InputAdornment, IconButton } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';


function PromptField({addMessage}) {
    const [inputValue, setInputValue] = useState('');
    const inputHandler = () => { 
        if (inputValue.length > 0) 
            addMessage(inputValue) 
        setInputValue('')
    }   

    return (
        <TextField
            id="prompt-text-field"
            variant="outlined"
            placeholder='Type Something'
            multiline
            sx={{
                width: '80%',
                height: '15vh',
                margin: '3vh 0',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                input: { color: 'var(--white)'},
                '& textarea': { 
                        color: 'var(--white)',
                },
            }}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            InputProps={{
                endAdornment: (
                    <InputAdornment position='end'>
                        <IconButton onClick={inputHandler}>
                            <SendIcon sx={{color: 'var(--light-grey)'}}/>
                        </IconButton>
                    </InputAdornment>
                ),
            }}
        />
    );
}

export default PromptField;