import React, { } from 'react';
import {
    List, ListSubheader, ListItem, ListItemText
} from '@mui/material';
import { } from '@mui/icons-material';


const collectionItemStyle = {
    ml: '8px'
}

const mockCollections = {
    'base': ["Web Testing", "IoT Testing", "Linux"],
    'user': ["IP Camera Security"]
}


function CollectionItem({collection}) {
    return (
        <ListItem sx={collectionItemStyle}>
            <ListItemText primary={collection}/>
        </ListItem>
    );
}


function CollectionList({owner}) {
    const renderCollections = () => {
        return mockCollections[owner].map((collection, idx) => {
            return <CollectionItem
                key={idx} 
                collection={collection}
            />
        });
    }

    return (
        <List 
            component="div" 
            subheader={
                <ListSubheader component="div" sx = {{
                        bgcolor: 'var(--grey)', 
                        color: 'var(--light-grey)'
                    }}
                >
                    {owner}
                </ListSubheader>
            }
        >
            {renderCollections()}
        </List>
    );
}

export default CollectionList;