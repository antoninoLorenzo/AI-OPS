import '../css/shared.css';
import '../css/scrollbar.css';

import { Grid } from '@mui/material';
import Sessions from './control_panel/Sessions';
import Knowlege from './control_panel/Knowlege';
import Tasks from './control_panel/Tasks';


const controlPanelStyle = { 
    width: '20vw', 
    height: '100vh',
    display: 'flex', 
    flexDirection: 'column', 
    justifyContent: 'start',
    overflowY: 'auto',
    overflowX: 'hidden',
    bgcolor: 'var(--black)', 
}


export default function ControlPanel() {

    return (
        <Grid item sx={controlPanelStyle}>
            <Sessions/>
            <Knowlege/>
            <Tasks/>
        </Grid>
    );
}