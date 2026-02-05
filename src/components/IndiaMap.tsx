import React from 'react';
import {useCurrentFrame, random, interpolate} from 'remotion';

// India map represented as a dot matrix (1 = land, 0 = water)
// Simplified representation of India's shape
const indiaMapData: number[][] = [
	[0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0],
	[0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
	[0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0],
	[0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0],
	[0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
	[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
	[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
	[0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
	[0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0],
	[0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0],
	[0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
];

const DOT_SIZE = 8;
const DOT_GAP = 12;
const GRAY_COLOR = '#555555';
const ORANGE_COLOR = '#ff6b35';

interface DotProps {
	row: number;
	col: number;
	isLand: boolean;
	frame: number;
}

const Dot: React.FC<DotProps> = ({row, col, isLand, frame}) => {
	if (!isLand) return null;

	// Use deterministic random based on position
	const seed = `dot-${row}-${col}`;
	const randomValue = random(seed);

	// Each dot has a random "activation time" and "duration"
	const activationCycle = Math.floor(randomValue * 60) + 20;
	const activationOffset = Math.floor(random(`${seed}-offset`) * 90);

	// Calculate if this dot should be orange at current frame
	const cyclePosition = (frame + activationOffset) % activationCycle;
	const isActive = cyclePosition < 15 && random(`${seed}-${Math.floor(frame / activationCycle)}`) > 0.6;

	// Fade in the entire map
	const mapOpacity = interpolate(frame, [0, 30], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});

	// Glow effect for active dots
	const glowIntensity = isActive
		? interpolate(cyclePosition, [0, 7, 15], [0, 1, 0], {
				extrapolateLeft: 'clamp',
				extrapolateRight: 'clamp',
		  })
		: 0;

	return (
		<div
			style={{
				position: 'absolute',
				left: col * DOT_GAP,
				top: row * DOT_GAP,
				width: DOT_SIZE,
				height: DOT_SIZE,
				borderRadius: '50%',
				backgroundColor: isActive ? ORANGE_COLOR : GRAY_COLOR,
				opacity: mapOpacity,
				boxShadow: isActive
					? `0 0 ${8 * glowIntensity}px ${4 * glowIntensity}px ${ORANGE_COLOR}`
					: 'none',
				transition: 'background-color 0.1s',
			}}
		/>
	);
};

export const IndiaMap: React.FC = () => {
	const frame = useCurrentFrame();

	const mapWidth = indiaMapData[0].length * DOT_GAP;
	const mapHeight = indiaMapData.length * DOT_GAP;

	return (
		<div
			style={{
				position: 'relative',
				width: mapWidth,
				height: mapHeight,
			}}
		>
			{indiaMapData.map((row, rowIndex) =>
				row.map((cell, colIndex) => (
					<Dot
						key={`${rowIndex}-${colIndex}`}
						row={rowIndex}
						col={colIndex}
						isLand={cell === 1}
						frame={frame}
					/>
				))
			)}
		</div>
	);
};
