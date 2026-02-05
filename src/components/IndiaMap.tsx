import React from 'react';
import {useCurrentFrame, random, interpolate} from 'remotion';

// India map - proper vertical shape with peninsula pointing down
// 1 = land, 0 = water
const indiaMapData: number[][] = [
	//         Kashmir/North region
	[0,0,0,0,0,0,0,0,0,1,1,1,1,1,0,0,0,0,0,0,0,0],
	[0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,0,0,0,0,0,0,0],
	[0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0],
	[0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0],
	//         Northern plains - wider
	[0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0],
	[0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0],
	[0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
	[0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
	//         Widest part - central India
	[0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
	[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
	[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
	[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
	[0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
	//         Starting to narrow - Deccan
	[0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
	[0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0],
	[0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0],
	[0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0],
	//         Peninsula narrowing
	[0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0],
	[0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0],
	[0,0,0,0,0,0,0,0,1,1,1,1,1,1,0,0,0,0,0,0,0,0],
	[0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0],
	//         Southern tip
	[0,0,0,0,0,0,0,0,0,0,1,1,0,0,0,0,0,0,0,0,0,0],
	[0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0],
];

const DOT_SIZE = 12;
const DOT_GAP = 16;
const GRAY_COLOR = '#555555';
const ORANGE_COLOR = '#ff6b35';

export const IndiaMap: React.FC = () => {
	const frame = useCurrentFrame();

	const mapWidth = indiaMapData[0].length * DOT_GAP;
	const mapHeight = indiaMapData.length * DOT_GAP;

	// Fade in the entire map
	const mapOpacity = interpolate(frame, [0, 30], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});

	return (
		<div
			style={{
				position: 'relative',
				width: mapWidth,
				height: mapHeight,
				opacity: mapOpacity,
			}}
		>
			{indiaMapData.map((row, rowIndex) =>
				row.map((cell, colIndex) => {
					if (cell === 0) return null;

					// Use deterministic random based on position
					const seed = `dot-${rowIndex}-${colIndex}`;
					const randomValue = random(seed);

					// Each dot has a random "activation time" and "duration"
					const activationCycle = Math.floor(randomValue * 40) + 25;
					const activationOffset = Math.floor(random(`${seed}-offset`) * 60);

					// Calculate if this dot should be orange at current frame
					const cycleFrame = Math.floor((frame + activationOffset) / activationCycle);
					const cyclePosition = (frame + activationOffset) % activationCycle;
					const isActive = cyclePosition < 18 && random(`${seed}-${cycleFrame}`) > 0.55;

					// Glow intensity for active dots
					const glowIntensity = isActive
						? interpolate(cyclePosition, [0, 9, 18], [0, 1, 0], {
								extrapolateLeft: 'clamp',
								extrapolateRight: 'clamp',
						  })
						: 0;

					return (
						<div
							key={`${rowIndex}-${colIndex}`}
							style={{
								position: 'absolute',
								left: colIndex * DOT_GAP,
								top: rowIndex * DOT_GAP,
								width: DOT_SIZE,
								height: DOT_SIZE,
								borderRadius: '50%',
								backgroundColor: isActive ? ORANGE_COLOR : GRAY_COLOR,
								boxShadow: isActive
									? `0 0 ${14 * glowIntensity}px ${7 * glowIntensity}px ${ORANGE_COLOR}`
									: 'none',
							}}
						/>
					);
				})
			)}
		</div>
	);
};
