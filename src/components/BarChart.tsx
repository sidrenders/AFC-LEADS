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

const CHART_WIDTH = 700;
const CHART_HEIGHT = 500;
const BAR_WIDTH = 65;
const BAR_GAP = 75;
const MAX_VALUE = 75;
const PADDING_LEFT = 60;
const PADDING_BOTTOM = 50;

export const BarChart: React.FC = () => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	return (
		<div
			style={{
				position: 'relative',
				width: CHART_WIDTH,
				height: CHART_HEIGHT + 100,
			}}
		>
			{/* Y-axis labels */}
			<div
				style={{
					position: 'absolute',
					left: 0,
					top: 0,
					height: CHART_HEIGHT,
					display: 'flex',
					flexDirection: 'column',
					justifyContent: 'space-between',
					alignItems: 'flex-end',
					width: PADDING_LEFT - 15,
					color: '#888',
					fontSize: 22,
					fontFamily: 'Arial, sans-serif',
				}}
			>
				<span>^</span>
				<span>75</span>
				<span>50</span>
				<span>25</span>
				<span>0</span>
			</div>

			{/* Y-axis line */}
			<div
				style={{
					position: 'absolute',
					left: PADDING_LEFT,
					top: CHART_HEIGHT,
					width: CHART_WIDTH - PADDING_LEFT,
					height: 3,
					backgroundColor: '#ffd700',
				}}
			/>

			{/* Bars */}
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

				const maxBarHeight = CHART_HEIGHT - 20;
				const targetHeight = (bar.value / MAX_VALUE) * maxBarHeight;
				const barHeight = interpolate(progress, [0, 1], [0, targetHeight], {
					extrapolateLeft: 'clamp',
					extrapolateRight: 'clamp',
				});

				const labelOpacity = interpolate(frame - delay - 10, [0, 15], [0, 1], {
					extrapolateLeft: 'clamp',
					extrapolateRight: 'clamp',
				});

				const barX = PADDING_LEFT + 20 + index * (BAR_WIDTH + BAR_GAP);
				const barY = CHART_HEIGHT - barHeight;

				return (
					<React.Fragment key={index}>
						{/* Bar */}
						<div
							style={{
								position: 'absolute',
								left: barX,
								top: barY,
								width: BAR_WIDTH,
								height: barHeight,
								backgroundColor: bar.color,
								borderRadius: '4px 4px 0 0',
							}}
						/>

						{/* Label above bar */}
						<div
							style={{
								position: 'absolute',
								left: barX + BAR_WIDTH / 2,
								top: barY - 30,
								transform: 'translateX(-50%)',
								color: bar.color,
								fontSize: 18,
								fontFamily: 'Arial, sans-serif',
								fontWeight: 'bold',
								opacity: labelOpacity,
								whiteSpace: 'nowrap',
							}}
						>
							{bar.label}
						</div>

						{/* Circle with value for first bar */}
						{index === 0 && (
							<div
								style={{
									position: 'absolute',
									left: barX + BAR_WIDTH + 15,
									top: barY - 25,
									display: 'flex',
									alignItems: 'center',
									gap: 10,
									opacity: labelOpacity,
								}}
							>
								<div
									style={{
										width: 45,
										height: 45,
										borderRadius: '50%',
										background:
											'radial-gradient(circle at 30% 30%, #ffffff, #cccccc)',
										boxShadow: '2px 2px 10px rgba(0,0,0,0.4)',
									}}
								/>
								<span
									style={{
										color: '#ffffff',
										fontSize: 38,
										fontFamily: 'Arial, sans-serif',
										fontWeight: 'bold',
									}}
								>
									7.3
								</span>
							</div>
						)}
					</React.Fragment>
				);
			})}

			{/* X-axis label */}
			<div
				style={{
					position: 'absolute',
					left: PADDING_LEFT + (CHART_WIDTH - PADDING_LEFT) / 2,
					top: CHART_HEIGHT + 30,
					transform: 'translateX(-50%)',
					color: '#ffd700',
					fontSize: 20,
					fontFamily: 'Arial, sans-serif',
					fontStyle: 'italic',
				}}
			>
				Income Class (in CR.)
			</div>
		</div>
	);
};
