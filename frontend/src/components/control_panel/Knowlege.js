import React, {useState} from 'react';
import {
    Collapse, Backdrop,
    List, ListSubheader, ListItem, 
    ListItemButton, ListItemText, ListItemIcon, 
    TextField, Button, FormControl, FormLabel
} from '@mui/material';
import { ExpandLess, ExpandMore, Add } from '@mui/icons-material';
import CollectionList from './CollectionList';


function KnowlegeButton({state}) {
    const [open, setOpen] = state;

    const handleClick = () => {
        setOpen(!open);
    };

    return (
        <ListItemButton onClick={handleClick} sx={{color: 'var(--white)'}}>
            <ListItemText primary="Knowlege" />
            {open ? <ExpandLess/> : <ExpandMore />}
        </ListItemButton>
    );
}

function AddCollectionForm({open, closeForm}) {
    return (
        <Backdrop
            sx={{ color: '#fff', zIndex: (theme) => theme.zIndex.drawer + 1 }}
            open={open}
            onClick={closeForm}
        >
            <FormControl sx={{backgroundColor: 'var(--black)'}}>
                <FormLabel sx={{color: 'var(--white)'}}>Title</FormLabel>
                <TextField 
                    value={"Enter Title"}
                    sx ={{
                        input: { color: 'var(--light-grey)'},
                        '& textarea': { 
                                color: 'var(--white)',
                        },
                    }}
                />
                <Button 
                    sx={{color: 'var(--white)', backgroundColor: 'var(--grey)', padding: '12px 24px', boxShadow: 1}}
                >
                    <Add/>Create
                </Button>
            </FormControl>
        </Backdrop>
    );
}

function AddCollectionButton() {
    const [formOpen, setFormOpen] = React.useState(false);
    const closeAddCollectionForm = () => { setFormOpen(false); };
    const openAddCollectionForm = () => { setFormOpen(true); };

    return (
        <ListItemButton
            onClick={openAddCollectionForm}
        >
            <AddCollectionForm open={formOpen} closeForm={closeAddCollectionForm}/>
            <ListItemText primary="Add Collection"/>
            <ListItemIcon 
                sx={{color: 'var(--white)', justifyContent: 'center'}}
            >
                <Add/>
            </ListItemIcon>
        </ListItemButton>
    );
}


export default function Knowlege() {
    const [open, setOpen] = React.useState(false);

    return (
        <List>
            <KnowlegeButton state={[open, setOpen]}/>
            <Collapse 
                in={open} 
                timeout="auto" 
                unmountOnExit 
                sx={{color: 'var(--white)'}}
            >
                <List component="div" disablePadding>
                    <AddCollectionButton/>
                    <CollectionList owner={'base'}/>
                    <CollectionList owner={'user'}/>
                </List>
            </Collapse>
        </List>
    );
}