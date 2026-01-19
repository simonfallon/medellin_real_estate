
import { describe, it, expect } from 'vitest';
import { parsePrice, formatPrice, parseArea, getBarrioFromLocation, getSourceName } from '../utils.js';

describe('Utils', () => {
    describe('parsePrice', () => {
        it('should return number if input is number', () => {
            expect(parsePrice(1000)).toBe(1000);
        });

        it('should parse string with dots', () => {
            expect(parsePrice('1.200.000')).toBe(1200000);
        });

        it('should parse string with $ sign and dots', () => {
            expect(parsePrice('$1.200.000')).toBe(1200000);
        });

        it('should handle empty or invalid input', () => {
            expect(parsePrice('')).toBe(0);
            expect(parsePrice(null)).toBe(0);
            expect(parsePrice(undefined)).toBe(0);
            expect(parsePrice('abc')).toBe(0);
        });
    });

    describe('formatPrice', () => {
        it('should format number with apostrophes', () => {
            expect(formatPrice(1200000)).toBe("$1'200'000");
        });

        it('should format string input', () => {
            expect(formatPrice('1200000')).toBe("$1'200'000");
        });

        it('should handle zero', () => {
            expect(formatPrice(0)).toBe("$0");
        });
    });

    describe('parseArea', () => {
        it('should parse simple number string', () => {
            expect(parseArea('72')).toBe(72);
        });

        it('should parse string with units', () => {
            expect(parseArea('72 m2')).toBe(72);
            expect(parseArea('72.50 mts')).toBe(73); // Rounds
        });

        it('should handle decimals by rounding', () => {
            expect(parseArea('72.4')).toBe(72);
            expect(parseArea('72.6')).toBe(73);
        });
    });

    describe('getBarrioFromLocation', () => {
        it('should return empty string for empty input', () => {
            expect(getBarrioFromLocation('')).toBe('');
        });

        it('should extract first valid part', () => {
            expect(getBarrioFromLocation('El Poblado, Medellin')).toBe('El Poblado');
        });

        it('should ignore blacklisted words like Medellin', () => {
            expect(getBarrioFromLocation('Medellin, Laureles')).toBe('Laureles');
        });

        it('should handle " - " separator', () => {
            expect(getBarrioFromLocation('Envigado - La Magnolia')).toBe('La Magnolia');
        });

        it('should be case insensitive for blacklisted words', () => {
            expect(getBarrioFromLocation('medellin, Belen')).toBe('Belen');
        });
    });

    describe('getSourceName', () => {
        it('should return mapped name', () => {
            expect(getSourceName('alberto_alvarez')).toBe('Alberto Álvarez');
        });

        it('should return original slug if not mapped', () => {
            expect(getSourceName('unknown_source')).toBe('unknown_source');
        });
    });
});
