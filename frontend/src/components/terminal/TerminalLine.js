import '../../css/shared.css';
import React from 'react';
import {
    TextField,
    ListItem
} from '@mui/material';
import { styled } from 'styled-components';
import PropTypes from 'prop-types';


const PromptSymbol = styled.span`
    margin-right: 0.25em;
    white-space: pre;
    color: ${({ theme }) => theme.promptSymbolColor};
`;


const TerminalLine = ({ theme, isInput }) => {
    const textFieldProps = {
        variant: "standard",
        sx: {
            width: '100%',
            '& textarea': {
                color: theme.outputColor,
            },
        },
        InputProps: {
            disableUnderline: true,
        },
    };

    if (isInput) {
        textFieldProps.InputProps.color = theme.commandColor;
        textFieldProps.InputProps.multiline = false; 
        textFieldProps.InputProps.readOnly = false; 
        return (
            <ListItem>
                <PromptSymbol theme={theme}>{theme.promptSymbol}</PromptSymbol>
                <TextField {...textFieldProps} />
            </ListItem>
        );
    } else {
        textFieldProps.defaultValue = 'val'; 
        textFieldProps.InputProps.multiline = true; 
        textFieldProps.InputProps.readOnly = true; 
        return (
            <ListItem>
                <TextField {...textFieldProps} />
            </ListItem>
        );
    }
};


TerminalLine.propTypes = {
    theme: PropTypes.object.isRequired,
    isInput: PropTypes.bool.isRequired
}

export default TerminalLine;
