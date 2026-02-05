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
					flex: 1,
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'center',
				}}
			>
				<div style={{width: '100%', height: '80%'}}>
					<BarChart />
				</div>
			</div>

			{/* Right side - India Map */}
			<div
				style={{
					flex: 0.6,
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'center',
					paddingRight: 60,
				}}
			>
				<IndiaMap />
			</div>
		</AbsoluteFill>
	);
};
