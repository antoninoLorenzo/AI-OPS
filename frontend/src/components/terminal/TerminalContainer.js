
import styled from 'styled-components';


const TerminalContainer = styled.div`
    color: ${({ theme }) => theme.outputColor};
    background: ${({ theme }) => theme.background};
    overflow-y: scroll;
    & > :last-child {
        padding-bottom: ${({ theme }) => theme.spacing};
    }
`;

export default TerminalContainer;