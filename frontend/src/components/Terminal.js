import '../css/shared.css';
import React, {useState, useContext} from 'react';
import {
    Grid,
    List
} from '@mui/material';
import PropTypes from 'prop-types';
import TerminalLine from './terminal/TerminalLine';
import TerminalContainer from './terminal/TerminalContainer';


const terminalThemeDefault = {
    background: 'var(--black)',
    commandColor: 'var(--white)',
    outputColor: 'var(--white)',
    errorOutputColor: '#ff89bd',
    promptSymbolColor: '#6effe6',
    promptSymbol: '>',    
}


function Terminal({theme}) {
    const [termIn, setTermIn] = useState([

    ]);
    const [termOut, setTermOut] = useState([

    ]);
    let terminalTheme = terminalThemeDefault;

    if (theme != undefined)
        terminalTheme = theme;

    return (
        <Grid sx={{
            width: '80vw', 
            padding: '0 3%', 
            bgcolor: 'var(--grey)',
        }}>
            <TerminalContainer 
                theme={terminalTheme}
                style={{
                    height: '90vh',
                    margin: '4% 0',
                    borderRadius: '8px',
                    fontSize: '1.1rem',
                    fontFamily: 'monospace',
                }}>
                <List>
                    <TerminalLine theme={terminalTheme} isInput={true}></TerminalLine>
                    <TerminalLine theme={terminalTheme} isInput={false}></TerminalLine>
                </List>
            </TerminalContainer>
        </Grid>
    );
}

Terminal.propTypes = {
    theme: PropTypes.object,
}

export default Terminal;

