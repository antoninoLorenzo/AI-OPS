import '../css/shared.css';
import React, {} from 'react';
import {Grid} from '@mui/material';
import ControlPanel from './ControlPanel';
import ChatBox from './ChatBox';
import Terminal from './Terminal';



export default function App() {
    return (
        <>
            <Grid container>
                <ControlPanel/>
                <ChatBox/>
            </Grid>
        </>
    );
}

