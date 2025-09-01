export function getBusinessDayBefore(date = new Date()) {
	const result = new Date(date);
	result.setDate(result.getDate() - 1);

	while (result.getDay() === 0 || result.getDay() === 6) {
		result.setDate(result.getDate() - 1);
	}

	return result;
}

export function getFirstDayOfYear(year = new Date().getFullYear()) {
	return new Date(year, 0, 1); // January 1st of the given year
}
