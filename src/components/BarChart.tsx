import React from 'react';
import {useCurrentFrame, interpolate, spring, useVideoConfig} from 'remotion';

interface BarData {
	label: string;
	value: number;
	color: string;
}

const bars: BarData[] = [
	{label: '<₹8,000', value: 7.3, color: '#ff5733'},
	{label: '<₹18,000', value: 65, color: '#ffa500'},
	{label: '~₹60,000', value: 55, color: '#ffd700'},
	{label: '~₹1L', value: 12, color: '#7cb342'},
	{label: '~₹5L', value: 4, color: '#4a90d9'},
];

export const BarChart: React.FC = () => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	return (
		<div
			style={{
				display: 'flex',
				flexDirection: 'column',
				height: '100%',
				padding: '40px 60px',
				boxSizing: 'border-box',
			}}
		>
			{/* Chart area */}
			<div
				style={{
					display: 'flex',
					flex: 1,
					position: 'relative',
				}}
			>
				{/* Y-axis */}
				<div
					style={{
						display: 'flex',
						flexDirection: 'column',
						justifyContent: 'space-between',
						alignItems: 'flex-end',
						paddingRight: 15,
						paddingBottom: 40,
						color: '#888',
						fontSize: 20,
						fontFamily: 'Arial, sans-serif',
					}}
				>
					<span>^</span>
					<span>75</span>
					<span>50</span>
					<span>25</span>
					<span>0</span>
				</div>

				{/* Bars container */}
				<div
					style={{
						display: 'flex',
						flex: 1,
						alignItems: 'flex-end',
						gap: 40,
						paddingLeft: 20,
						borderBottom: '3px solid #ffd700',
						position: 'relative',
					}}
				>
					{bars.map((bar, index) => {
						const delay = index * 5;
						const progress = spring({
							fps,
							frame: frame - delay,
							config: {
								damping: 50,
								stiffness: 100,
								mass: 0.5,
							},
						});

						const barHeight = interpolate(
							progress,
							[0, 1],
							[0, (bar.value / 75) * 100],
							{
								extrapolateLeft: 'clamp',
								extrapolateRight: 'clamp',
							}
						);

						const labelOpacity = interpolate(
							frame - delay - 15,
							[0, 10],
							[0, 1],
							{
								extrapolateLeft: 'clamp',
								extrapolateRight: 'clamp',
							}
						);

						return (
							<div
								key={index}
								style={{
									display: 'flex',
									flexDirection: 'column',
									alignItems: 'center',
									position: 'relative',
								}}
							>
								{/* Value label above bar */}
								<div
									style={{
										color: bar.color,
										fontSize: 18,
										fontFamily: 'Arial, sans-serif',
										fontWeight: 'bold',
										marginBottom: 8,
										opacity: labelOpacity,
										whiteSpace: 'nowrap',
									}}
								>
									{bar.label}
								</div>

								{/* Bar */}
								<div
									style={{
										width: 60,
										height: `${barHeight}%`,
										backgroundColor: bar.color,
										borderRadius: '4px 4px 0 0',
										minHeight: 2,
									}}
								/>

								{/* Circle with value for first bar */}
								{index === 0 && (
									<div
										style={{
											position: 'absolute',
											left: 70,
											bottom: `${barHeight}%`,
											display: 'flex',
											alignItems: 'center',
											gap: 8,
											opacity: labelOpacity,
										}}
									>
										<div
											style={{
												width: 40,
												height: 40,
												borderRadius: '50%',
												background:
													'radial-gradient(circle at 30% 30%, #ffffff, #cccccc)',
												boxShadow: '2px 2px 8px rgba(0,0,0,0.3)',
											}}
										/>
										<span
											style={{
												color: '#ffffff',
												fontSize: 32,
												fontFamily: 'Arial, sans-serif',
												fontWeight: 'bold',
											}}
										>
											{bar.value}
										</span>
									</div>
								)}
							</div>
						);
					})}
				</div>
			</div>

			{/* X-axis label */}
			<div
				style={{
					textAlign: 'center',
					color: '#ffd700',
					fontSize: 20,
					fontFamily: 'Arial, sans-serif',
					fontStyle: 'italic',
					marginTop: 20,
					paddingLeft: 50,
				}}
			>
				Income Class (in CR.)
			</div>
		</div>
	);
};
