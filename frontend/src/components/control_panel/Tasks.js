import React, {useState} from 'react';
import {
    Collapse, Typography,
    List, ListItemButton, ListItemText,
} from '@mui/material';

import {
    Timeline, TimelineItem, timelineItemClasses, TimelineSeparator, 
    TimelineConnector, TimelineContent, TimelineDot
} from '@mui/lab';
import { ExpandLess, ExpandMore } from '@mui/icons-material';
import { Task, TaskStatus } from './Task';


function TasksButton({state}) {
    const [open, setOpen] = state;

    const handleClick = () => {
        setOpen(!open);
    };

    return (
        <ListItemButton onClick={handleClick} sx={{color: 'var(--white)'}}>
            <ListItemText primary="Tasks" />
            {open ? <ExpandLess/> : <ExpandMore />}
        </ListItemButton>
    );
}

function TaskItem({task, last}) {
    return (
        <TimelineItem>
            <TimelineSeparator>
                {task.taskStatus > -1 ? <TimelineDot variant="outlined"/> : <TimelineDot/>}
                {last ? <TimelineConnector/> : undefined}
            </TimelineSeparator>
            <TimelineContent>
                {task.name}
                <Typography sx={{
                        height: '10px',
                        color: 'var(--light-grey)'
                    }} 
                    variant="caption" 
                    display="block" 
                >
                    {task.getStatusName()}
                </Typography>
            </TimelineContent>
        </TimelineItem>   
    );
} 


export default function Tasks() {
    const [open, setOpen] = useState(false);
    const [tasks, setTasks] = useState([
        new Task('Task 1'),
        new Task('Task 2')
    ]);

    const renderTasks = () => {
        return tasks.map((item, index) => (
            <TaskItem key={index} task={item} last={index < tasks.length - 1}/>
        ));
    }

    return (
        <List>
            <TasksButton state={[open, setOpen]}/>
            <Collapse
                in={open} 
                timeout="auto" 
                unmountOnExit 
                sx={{color: 'var(--white)'}}
            >
                <Timeline
                    sx={{
                        [`& .${timelineItemClasses.root}:before`]: {
                            flex: 0,
                            padding: 0,
                        },
                    }}
                >
                    {renderTasks()}
                </Timeline>
            </Collapse>
        </List>
    );
}