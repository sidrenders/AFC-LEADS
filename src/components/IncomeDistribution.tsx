import React from 'react';
import {AbsoluteFill} from 'remotion';
import {BarChart} from './BarChart';
import {IndiaMap} from './IndiaMap';

export const IncomeDistribution: React.FC = () => {
	return (
		<AbsoluteFill
			style={{
				backgroundColor: '#1a1a1a',
			}}
		>
			{/* Left side - Bar Chart */}
			<div
				style={{
					position: 'absolute',
					left: 40,
					bottom: 80,
				}}
			>
				<BarChart />
			</div>

			{/* Right side - India Map */}
			<div
				style={{
					position: 'absolute',
					right: 150,
					top: '50%',
					transform: 'translateY(-50%)',
				}}
			>
				<IndiaMap />
			</div>
		</AbsoluteFill>
	);
};
