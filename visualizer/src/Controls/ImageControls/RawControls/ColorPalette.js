/** Modified from https://github.com/hms-dbmi/viv */
import IconButton from '@material-ui/core/IconButton';
import { makeStyles } from '@material-ui/core/styles';
import LensIcon from '@material-ui/icons/Lens';
import React from 'react';

// TODO: move to constants
const COLOR_PALLETE = [
  '#0000FF',
  '#00FF00',
  '#FF00FF',
  '#FFFF00',
  '#FF8000',
  '#00FFFF',
  '#FFFFFF',
  '#FF0000',
];

const useStyles = makeStyles(() => ({
  container: {
    width: '70px',
    height: '40px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  button: {
    padding: '3px',
    width: '16px',
    height: '16px',
  },
  icon: {
    width: '17px',
    height: '17px',
    // border: '1px solid black',
    // borderRadius: '50%'
  },
}));

const ColorPalette = ({ handleChange }) => {
  const classes = useStyles();
  return (
    <div className={classes.container} aria-label='color-swatch'>
      {COLOR_PALLETE.map(color => {
        return (
          <IconButton
            className={classes.button}
            key={color}
            onClick={() => handleChange(color)}
          >
            <LensIcon
              fontSize='small'
              style={{ color: `${color}` }}
              className={classes.icon}
            />
          </IconButton>
        );
      })}
    </div>
  );
};

export default ColorPalette;
