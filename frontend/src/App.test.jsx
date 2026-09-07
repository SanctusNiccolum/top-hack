import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from './App';

describe('payment score landing page', () => {
  it('renders the main promise and both progressive sections', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: /платформа управления/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /возможности сервиса/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /отвечаем на вопросы/i })).toBeInTheDocument();
  });

  it('renders FAQ items as accessible native disclosures', () => {
    render(<App />);
    expect(screen.getByText('Что такое альтернативный скоринг?')).toBeInTheDocument();
    expect(screen.getAllByRole('group')).toHaveLength(0);
  });
});
