import React from 'react';
import {AbsoluteFill} from 'remotion';
import {BarChart} from './BarChart';
import {IndiaMap} from './IndiaMap';

export const IncomeDistribution: React.FC = () => {
	return (
		<AbsoluteFill
			style={{
				backgroundColor: '#1a1a1a',
				display: 'flex',
				flexDirection: 'row',
			}}
		>
			{/* Left side - Bar Chart */}
			<div
				style={{
					flex: 1.2,
					display: 'flex',
					alignItems: 'flex-end',
					justifyContent: 'flex-start',
					paddingBottom: 100,
				}}
			>
				<BarChart />
			</div>

			{/* Right side - India Map */}
			<div
				style={{
					flex: 0.8,
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'center',
					paddingRight: 80,
				}}
			>
				<IndiaMap />
			</div>
		</AbsoluteFill>
	);
};
