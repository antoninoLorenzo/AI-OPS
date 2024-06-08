import '../../css/shared.css';
import React, { useState } from 'react';

import {
    List, ListSubheader, ListItem, ListItemButton, ListItemText,
    Menu, MenuItem, IconButton,
    Divider
} from '@mui/material';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

const sessionListItemStyle = {
    color: 'var(--white)',
}

const sessionMenuItemStyle = {
    width: '20px', 
    height: '20px', 
    color: 'var(--grey)', 
    mr: '8px'
}

function SessionMenuItem({commandName}) {
    const commands = {
        "Rename": <EditIcon sx={sessionMenuItemStyle}/>,
        "Delete": <DeleteIcon sx={sessionMenuItemStyle}/>
    }
    return (
        <MenuItem sx={{fontSize:'14px'}}>
            {commands[commandName]} {commandName}
        </MenuItem>
    );
}

function SessionMenu({sessionIdx, menuStates, closeMenu}) {
    return (
        <Menu
            sx={{boxShadow: 2}}
            anchorEl={menuStates[sessionIdx].anchorEl}
            open={menuStates[sessionIdx].visible}
            onClose={() => closeMenu(sessionIdx)}
            MenuListProps={{
                'aria-labelledby': "menu-" + sessionIdx,
            }}
        >
            <SessionMenuItem commandName={"Rename"}/>
            <SessionMenuItem commandName={"Delete"}/>
        </Menu>
    );
}


export default function Sessions() {
    const [sessions, setSessions] = useState([
        "IP Camera",
        "Web App"
    ])
    
    const [menuStates, setMenuStates] = useState(
        sessions.reduce((acc, _, index) => ({...acc, 
            [index]: {visible: false, anchorEl: null}}), {}
        )
    );

    const handleMenuOpen = (index, event) => {
        setMenuStates(prevState => ({
           ...prevState,
            [index]: {...prevState[index], visible: true, anchorEl: event.currentTarget}
        }));
    };

    const handleMenuClose = (index) => {
        setMenuStates(prevState => ({
           ...prevState,
            [index]: {...prevState[index], visible: false, anchorEl: null}
        }));
    };


    const renderSessions = () => {
        return sessions.map((item, index) => (
            <ListItem key={index} disablePadding>
                <ListItemButton>
                    <ListItemText primary={item} sx={sessionListItemStyle} />
                    <IconButton 
                        onClick={(event) => handleMenuOpen(index, event)}  
                        id={"menu-" + index}
                        sx={{width: '28px', height: '28px', color: 'var(--light-grey)'}}
                    >
                        <MoreHorizIcon/>
                    </IconButton>
                    <SessionMenu 
                        sessionIdx={index} 
                        menuStates={menuStates} 
                        closeMenu={handleMenuClose}
                    />
                </ListItemButton>
            </ListItem>
        ));
    };

    return (
        <List
            sx={{mt: '1.5rem'}}
            subheader={
                <ListSubheader component="div" sx = {{bgcolor: 'var(--black)', color: 'var(--light-grey)'}}>
                    Sessions
                </ListSubheader>
            }
        >
            {renderSessions()}
        </List>
    );
}