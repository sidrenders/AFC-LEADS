import {Composition} from 'remotion';
import {IncomeDistribution} from './components/IncomeDistribution';

export const RemotionRoot: React.FC = () => {
	return (
		<>
			<Composition
				id="IncomeDistribution"
				component={IncomeDistribution}
				durationInFrames={180}
				width={1920}
				height={1080}
				fps={30}
				defaultProps={{}}
			/>
		</>
	);
};
