import React from 'react';
import {useCurrentFrame, interpolate, spring, useVideoConfig} from 'remotion';

interface BarData {
	label: string;
	value: number;
	color: string;
}

const bars: BarData[] = [
	{label: '<₹8,000', value: 10, color: '#ff5733'},
	{label: '<₹18,000', value: 65, color: '#ffa500'},
	{label: '~₹60,000', value: 55, color: '#ffd700'},
	{label: '~₹1L', value: 15, color: '#7cb342'},
	{label: '~₹5L', value: 5, color: '#4a90d9'},
];

const MAX_BAR_HEIGHT = 450;
const CHART_HEIGHT = 550;

export const BarChart: React.FC = () => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	return (
		<div
			style={{
				display: 'flex',
				flexDirection: 'column',
				height: '100%',
				width: '100%',
				paddingTop: 60,
				paddingLeft: 40,
				boxSizing: 'border-box',
			}}
		>
			{/* Chart area */}
			<div
				style={{
					display: 'flex',
					height: CHART_HEIGHT,
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
						height: CHART_HEIGHT - 40,
						color: '#888',
						fontSize: 24,
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
						alignItems: 'flex-end',
						gap: 50,
						paddingLeft: 30,
						paddingBottom: 40,
						borderBottom: '3px solid #ffd700',
						height: CHART_HEIGHT,
						position: 'relative',
					}}
				>
					{bars.map((bar, index) => {
						const delay = index * 8;
						const progress = spring({
							fps,
							frame: frame - delay,
							config: {
								damping: 50,
								stiffness: 80,
								mass: 0.8,
							},
						});

						const targetHeight = (bar.value / 75) * MAX_BAR_HEIGHT;
						const barHeight = interpolate(
							progress,
							[0, 1],
							[0, targetHeight],
							{
								extrapolateLeft: 'clamp',
								extrapolateRight: 'clamp',
							}
						);

						const labelOpacity = interpolate(
							frame - delay - 10,
							[0, 15],
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
									justifyContent: 'flex-end',
									position: 'relative',
									height: '100%',
								}}
							>
								{/* Value label above bar */}
								<div
									style={{
										position: 'absolute',
										bottom: barHeight + 50,
										color: bar.color,
										fontSize: 20,
										fontFamily: 'Arial, sans-serif',
										fontWeight: 'bold',
										opacity: labelOpacity,
										whiteSpace: 'nowrap',
									}}
								>
									{bar.label}
								</div>

								{/* Bar */}
								<div
									style={{
										width: 70,
										height: barHeight,
										backgroundColor: bar.color,
										borderRadius: '4px 4px 0 0',
										marginBottom: 40,
									}}
								/>

								{/* Circle with value for first bar */}
								{index === 0 && (
									<div
										style={{
											position: 'absolute',
											left: 80,
											bottom: barHeight + 50,
											display: 'flex',
											alignItems: 'center',
											gap: 10,
											opacity: labelOpacity,
										}}
									>
										<div
											style={{
												width: 50,
												height: 50,
												borderRadius: '50%',
												background:
													'radial-gradient(circle at 30% 30%, #ffffff, #cccccc)',
												boxShadow: '2px 2px 10px rgba(0,0,0,0.4)',
											}}
										/>
										<span
											style={{
												color: '#ffffff',
												fontSize: 42,
												fontFamily: 'Arial, sans-serif',
												fontWeight: 'bold',
											}}
										>
											7.3
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
					color: '#ffd700',
					fontSize: 22,
					fontFamily: 'Arial, sans-serif',
					fontStyle: 'italic',
					marginTop: 15,
					marginLeft: 250,
				}}
			>
				Income Class (in CR.)
			</div>
		</div>
	);
};
