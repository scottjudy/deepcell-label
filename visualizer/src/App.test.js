import { render, screen } from '@testing-library/react';
import App from './App';

test('renders DeepCell Label', () => {
  render(<App />);
  const linkElements = screen.getAllByText(/DeepCell Label/i);
  linkElements.map(el => expect(el).toBeInTheDocument());
});
